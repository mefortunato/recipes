from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId

from app.config import get_settings
from app.database import db_manager
from app.services.auth_service import decode_access_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    token = None

    # 1. Check Bearer token in Authorization header
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    # 2. Check access_token cookie
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in with Google.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]
    db = db_manager.db
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        )

    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        user = await db.users.find_one({"_id": user_id})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    settings = get_settings()
    user["_id"] = str(user["_id"])
    email = user.get("email", "")
    is_bootstrap = settings.is_privileged_email(email)

    if is_bootstrap:
        user["role"] = "admin"
        user["can_edit"] = True
        user["is_admin"] = True
        user["is_bootstrap"] = True
    else:
        role = user.get("role", "viewer")
        user["role"] = role
        user["is_admin"] = (role == "admin") or user.get("is_admin", False)
        user["can_edit"] = (role in ("admin", "editor")) or user.get("can_edit", False)
        user["is_bootstrap"] = False

    return user


async def get_optional_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[Dict[str, Any]]:
    try:
        return await get_current_user(request, auth_header)
    except HTTPException:
        return None


async def require_editor_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Ensures the authenticated user has permissions to create, edit, or delete recipes."""
    if not current_user.get("can_edit", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to add, edit, or delete recipes. Only authorized chefs/editors can modify recipes.",
        )
    return current_user


async def require_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Ensures the authenticated user has administrator / privileged permissions."""
    if not (current_user.get("is_admin", False) or current_user.get("role") == "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrator access required. You do not have permission to manage user roles.",
        )
    return current_user
