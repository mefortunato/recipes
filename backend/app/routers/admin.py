import logging
import re
from typing import Optional, Dict, Any, List
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.database import get_database
from app.dependencies.auth import require_admin_user
from app.models.user import (
    UserPublic,
    UserPermissionUpdate,
    UserCreateRequest,
    UserListResponse,
)
from app.services.auth_service import (
    LEGACY_PERMISSION_FIELDS,
    ROLES,
    resolve_permissions,
    revoke_all_sessions,
    stored_role,
    utc_now,
)

logger = logging.getLogger("recipe_book.admin")

router = APIRouter(prefix="/admin", tags=["Admin & User Permissions"])

# Upper bound on users returned by the admin list (roles are resolved per user in Python)
MAX_LISTED_USERS = 1000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


async def find_user_or_404(db: AsyncIOMotorDatabase, user_id: str) -> Dict[str, Any]:
    try:
        target = await db.users.find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        target = None
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID '{user_id}' not found")
    return target


async def save_role(db: AsyncIOMotorDatabase, user_id: Any, role: str) -> None:
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"role": role}, "$unset": LEGACY_PERMISSION_FIELDS},
    )


@router.get("/users", response_model=UserListResponse, summary="List all users with roles and permission status")
async def list_users(
    search: Optional[str] = Query(default=None, description="Search by email or name"),
    role: Optional[str] = Query(default=None, description="Filter by role: admin, editor, viewer"),
    current_admin: Dict[str, Any] = Depends(require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns registered users with their current roles and permissions.

    Role counts (and `total`) cover every user matching the search, regardless of the role filter,
    so the UI's role tabs stay accurate.
    """
    settings = get_settings()

    query = {}
    if search and search.strip():
        search_regex = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [{"email": search_regex}, {"name": search_regex}]

    cursor = db.users.find(query).sort("created_at", -1)
    raw_users = await cursor.to_list(length=MAX_LISTED_USERS)
    resolved = [resolve_permissions(u, settings) for u in raw_users]

    role_counts = {r: 0 for r in ROLES}
    for u in resolved:
        role_counts[u["role"]] += 1

    role_filter = role.lower() if role and role.lower() != "all" else None
    users: List[UserPublic] = [UserPublic(**u) for u in resolved if role_filter is None or u["role"] == role_filter]

    return UserListResponse(
        users=users,
        total=len(resolved),
        admin_count=role_counts["admin"],
        editor_count=role_counts["editor"],
        viewer_count=role_counts["viewer"],
    )


@router.patch("/users/{user_id}/permissions", response_model=UserPublic, summary="Modify permissions and role for a user")
async def update_user_permissions(
    user_id: str,
    update: UserPermissionUpdate,
    current_admin: Dict[str, Any] = Depends(require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Updates the role of a target user. `can_edit` is a shortcut that toggles between editor and viewer."""
    settings = get_settings()
    target = await find_user_or_404(db, user_id)
    target_email = target.get("email", "")

    if update.role:
        new_role = update.role.lower().strip()
        if new_role not in ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be one of: 'admin', 'editor', 'viewer'.",
            )
    elif update.can_edit is not None:
        current_role = stored_role(target)
        # Admins can always edit; toggling only moves non-admins between editor and viewer
        new_role = "admin" if current_role == "admin" else ("editor" if update.can_edit else "viewer")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specify either 'role' or 'can_edit' to update permissions.",
        )

    # Prevent demoting bootstrap admin configured in .env
    if settings.is_privileged_email(target_email) and new_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change role for '{target_email}'. This email is configured as a bootstrap administrator in ALLOWED_EDITOR_EMAILS (.env).",
        )

    # Prevent admin from demoting themselves if they are the only admin
    if str(target["_id"]) == str(current_admin["_id"]) and new_role != "admin":
        other_admins = await db.users.count_documents({
            "_id": {"$ne": target["_id"]},
            "role": "admin",
        })
        if other_admins == 0 and not any(e != target_email for e in settings.editor_emails_list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove administrator privileges from yourself when you are the sole administrator.",
            )

    await save_role(db, target["_id"], new_role)
    logger.info("Admin %s set role of %s to %s", current_admin.get("email"), target_email, new_role)
    target["role"] = new_role
    for field in LEGACY_PERMISSION_FIELDS:
        target.pop(field, None)
    return UserPublic(**resolve_permissions(target, settings))


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED, summary="Pre-authorize or provision a user by email")
async def provision_user(
    body: UserCreateRequest,
    current_admin: Dict[str, Any] = Depends(require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Allows an administrator to pre-provision a user email with an assigned role before their first sign-in."""
    settings = get_settings()
    email = body.email.strip().lower()

    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid email address is required.")

    role = body.role.strip().lower()
    if role not in ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'admin', 'editor', or 'viewer'.")

    existing = await db.users.find_one({"email": email})
    if existing:
        await save_role(db, existing["_id"], role)
        if body.name and not existing.get("name"):
            await db.users.update_one({"_id": existing["_id"]}, {"$set": {"name": body.name}})
            existing["name"] = body.name
        existing["role"] = role
        for field in LEGACY_PERMISSION_FIELDS:
            existing.pop(field, None)
        return UserPublic(**resolve_permissions(existing, settings))

    new_user = {
        "email": email,
        "name": body.name.strip() if body.name else email.split("@")[0],
        "picture": "",
        "google_id": None,
        "role": role,
        "created_at": utc_now(),
        "last_login": None,
    }
    result = await db.users.insert_one(new_user)
    new_user["_id"] = result.inserted_id
    return UserPublic(**resolve_permissions(new_user, settings))


@router.delete("/users/{user_id}", summary="Delete a registered user")
async def delete_user(
    user_id: str,
    current_admin: Dict[str, Any] = Depends(require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Deletes a user account from the system."""
    settings = get_settings()
    target = await find_user_or_404(db, user_id)

    if str(target["_id"]) == str(current_admin["_id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account.")

    if settings.is_privileged_email(target.get("email")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete bootstrap administrator configured in .env (ALLOWED_EDITOR_EMAILS).",
        )

    await db.users.delete_one({"_id": target["_id"]})
    logger.info("Admin %s deleted user %s", current_admin.get("email"), target.get("email"))
    return {"message": "User deleted successfully", "id": user_id}


@router.post("/users/{user_id}/revoke-sessions", summary="Sign a user out of every session")
async def revoke_user_sessions(
    user_id: str,
    current_admin: Dict[str, Any] = Depends(require_admin_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Invalidates all of a user's outstanding session tokens (e.g. after a lost device or suspected compromise)."""
    target = await find_user_or_404(db, user_id)
    await revoke_all_sessions(db, target["_id"])
    logger.info("Admin %s revoked all sessions for %s", current_admin.get("email"), target.get("email"))
    return {"message": "All sessions revoked", "id": user_id}
