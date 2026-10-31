from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.services.auth_service import decode_access_token, is_token_revoked, resolve_permissions

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    token = None

    # 1. Check Bearer token in Authorization header (API clients)
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    # 2. Check access_token cookie (browser sessions)
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

    try:
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    except (InvalidId, TypeError):
        user = None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    if await is_token_revoked(db, payload, user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This session has been signed out. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Expose the verified token claims so handlers like /logout can revoke this exact session
    request.state.token_payload = payload
    return resolve_permissions(user)


async def get_optional_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Optional[Dict[str, Any]]:
    try:
        return await get_current_user(request, auth_header, db)
    except HTTPException:
        return None


async def require_editor_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Ensures the authenticated user has permissions to create, edit, or delete recipes."""
    if not current_user["can_edit"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to add, edit, or delete recipes. Only authorized chefs/editors can modify recipes.",
        )
    return current_user


async def require_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Ensures the authenticated user has administrator / privileged permissions."""
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrator access required. You do not have permission to manage user roles.",
        )
    return current_user
