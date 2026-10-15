import logging
from typing import Optional, Dict, Any, List
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.database import db_manager
from app.dependencies.auth import require_admin_user
from app.models.user import (
    UserPublic,
    UserPermissionUpdate,
    UserCreateRequest,
    UserListResponse,
)
from app.services.auth_service import utc_now

logger = logging.getLogger("recipe_book.admin")

router = APIRouter(prefix="/admin", tags=["Admin & User Permissions"])


def normalize_user_doc(doc: Dict[str, Any], settings) -> Dict[str, Any]:
    """Helper to ensure user document has standard string ID, role, and permission flags."""
    doc["_id"] = str(doc["_id"])
    email = doc.get("email", "")
    is_bootstrap = settings.is_privileged_email(email)

    if is_bootstrap:
        doc["role"] = "admin"
        doc["can_edit"] = True
        doc["is_admin"] = True
        doc["is_bootstrap"] = True
    else:
        role = doc.get("role", "viewer")
        doc["role"] = role
        doc["is_admin"] = (role == "admin") or doc.get("is_admin", False)
        doc["can_edit"] = (role in ("admin", "editor")) or doc.get("can_edit", False)
        doc["is_bootstrap"] = False

    return doc


@router.get("/users", response_model=UserListResponse, summary="List all users with roles and permission status")
async def list_users(
    search: Optional[str] = Query(default=None, description="Search by email or name"),
    role: Optional[str] = Query(default=None, description="Filter by role: admin, editor, viewer"),
    current_admin: Dict[str, Any] = Depends(require_admin_user),
):
    """Returns all registered users in the database with their current roles and permissions."""
    db = db_manager.db
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    settings = get_settings()

    query = {}
    if search:
        search_regex = {"$regex": search.strip(), "$options": "i"}
        query["$or"] = [{"email": search_regex}, {"name": search_regex}]

    cursor = db.users.find(query).sort("created_at", -1)
    raw_users = await cursor.to_list(length=500)

    users: List[UserPublic] = []
    admin_count = 0
    editor_count = 0
    viewer_count = 0

    for u in raw_users:
        norm = normalize_user_doc(u, settings)

        # Count roles across all fetched users
        if norm["role"] == "admin":
            admin_count += 1
        elif norm["role"] == "editor":
            editor_count += 1
        else:
            viewer_count += 1

        # Apply role filter if requested
        if role and role.lower() != "all" and norm["role"] != role.lower():
            continue

        users.append(UserPublic(**norm))

    return UserListResponse(
        users=users,
        total=len(users),
        admin_count=admin_count,
        editor_count=editor_count,
        viewer_count=viewer_count,
    )


@router.patch("/users/{user_id}/permissions", response_model=UserPublic, summary="Modify permissions and role for a user")
async def update_user_permissions(
    user_id: str,
    update: UserPermissionUpdate,
    current_admin: Dict[str, Any] = Depends(require_admin_user),
):
    """Updates role or recipe editing permissions for a target user."""
    db = db_manager.db
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    settings = get_settings()

    try:
        user_query = {"_id": ObjectId(user_id)}
    except Exception:
        user_query = {"_id": user_id}

    target = await db.users.find_one(user_query)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID '{user_id}' not found")

    target_email = target.get("email", "")

    # Prevent demoting bootstrap admin configured in .env
    if settings.is_privileged_email(target_email) and update.role and update.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change role for '{target_email}'. This email is configured as a bootstrap administrator in ALLOWED_EDITOR_EMAILS (.env).",
        )

    # Prevent admin from demoting themselves if they are the only admin
    if str(target["_id"]) == str(current_admin["_id"]) and update.role and update.role.lower() != "admin":
        other_admins = await db.users.count_documents({
            "_id": {"$ne": target["_id"]},
            "role": "admin",
        })
        if other_admins == 0 and not any(e != target_email for e in settings.editor_emails_list if e != "*"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove administrator privileges from yourself when you are the sole administrator.",
            )

    # Calculate new values
    if update.role:
        new_role = update.role.lower().strip()
        if new_role not in ("admin", "editor", "viewer"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be one of: 'admin', 'editor', 'viewer'.",
            )
        new_is_admin = (new_role == "admin")
        new_can_edit = (new_role in ("admin", "editor")) if update.can_edit is None else update.can_edit
    elif update.can_edit is not None:
        new_can_edit = update.can_edit
        curr_role = target.get("role", "viewer")
        if new_can_edit and curr_role == "viewer":
            new_role = "editor"
        elif not new_can_edit and curr_role == "editor":
            new_role = "viewer"
        else:
            new_role = curr_role
        new_is_admin = (new_role == "admin")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specify either 'role' or 'can_edit' to update permissions.",
        )

    update_fields = {
        "role": new_role,
        "can_edit": new_can_edit,
        "is_admin": new_is_admin,
    }

    await db.users.update_one({"_id": target["_id"]}, {"$set": update_fields})
    target.update(update_fields)
    norm = normalize_user_doc(target, settings)
    return UserPublic(**norm)


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED, summary="Pre-authorize or provision a user by email")
async def provision_user(
    body: UserCreateRequest,
    current_admin: Dict[str, Any] = Depends(require_admin_user),
):
    """Allows an administrator to pre-provision a user email with an assigned role before their first sign-in."""
    db = db_manager.db
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    settings = get_settings()
    email = body.email.strip().lower()

    if not email or "@" not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid email address is required.")

    role = body.role.strip().lower()
    if role not in ("admin", "editor", "viewer"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role must be 'admin', 'editor', or 'viewer'.")

    is_admin = (role == "admin")
    can_edit = (role in ("admin", "editor"))

    existing = await db.users.find_one({"email": email})
    if existing:
        update_fields = {
            "role": role,
            "can_edit": can_edit,
            "is_admin": is_admin,
        }
        if body.name and not existing.get("name"):
            update_fields["name"] = body.name
        await db.users.update_one({"_id": existing["_id"]}, {"$set": update_fields})
        existing.update(update_fields)
        norm = normalize_user_doc(existing, settings)
        return UserPublic(**norm)

    new_user = {
        "email": email,
        "name": body.name.strip() if body.name else email.split("@")[0],
        "picture": "",
        "google_id": None,
        "role": role,
        "can_edit": can_edit,
        "is_admin": is_admin,
        "created_at": utc_now(),
        "last_login": None,
    }
    result = await db.users.insert_one(new_user)
    new_user["_id"] = str(result.inserted_id)
    norm = normalize_user_doc(new_user, settings)
    return UserPublic(**norm)


@router.delete("/users/{user_id}", summary="Delete a registered user")
async def delete_user(
    user_id: str,
    current_admin: Dict[str, Any] = Depends(require_admin_user),
):
    """Deletes a user account from the system."""
    db = db_manager.db
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    settings = get_settings()

    try:
        user_query = {"_id": ObjectId(user_id)}
    except Exception:
        user_query = {"_id": user_id}

    target = await db.users.find_one(user_query)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID '{user_id}' not found")

    if str(target["_id"]) == str(current_admin["_id"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account.")

    if settings.is_privileged_email(target.get("email")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete bootstrap administrator configured in .env (ALLOWED_EDITOR_EMAILS).",
        )

    await db.users.delete_one({"_id": target["_id"]})
    return {"message": "User deleted successfully", "id": user_id}
