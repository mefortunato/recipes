import logging
import urllib.parse
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status, Query
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.models.user import UserPublic, TokenResponse, GoogleVerifyRequest, AuthConfigResponse
from app.services.auth_service import (
    create_access_token,
    verify_google_credential,
    exchange_google_code,
    get_or_create_user,
    get_demo_user,
)
from app.dependencies.auth import get_current_user

logger = logging.getLogger("recipe_book.auth")

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])


@router.get("/config", response_model=AuthConfigResponse, summary="Get public authentication settings")
async def get_auth_config():
    """Returns public authentication parameters (e.g. Google Client ID, active permission rules)."""
    settings = get_settings()
    return AuthConfigResponse(
        google_client_id=settings.google_client_id or "",
        google_auth_enabled=bool(settings.google_client_id and settings.google_client_secret),
        dev_login_enabled=settings.allow_dev_login,
        allowed_editor_emails=settings.editor_emails_list,
    )


@router.get("/google/login", summary="Redirect to Google OAuth consent screen")
async def google_login(request: Request):
    """Generates the Google OAuth 2.0 authorization URL and redirects the browser."""
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GOOGLE_CLIENT_ID is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.",
        )

    base_url = settings.frontend_url.rstrip("/") if settings.frontend_url else str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/auth/google/callback"

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/google/callback", summary="Google OAuth authorization code callback")
async def google_callback(code: str, request: Request, response: Response):
    """Exchanges Google authorization code for credentials, creates or updates the user, and sets session cookie."""
    settings = get_settings()
    base_url = settings.frontend_url.rstrip("/") if settings.frontend_url else str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/auth/google/callback"

    user_info = await exchange_google_code(code, redirect_uri)
    if not user_info:
        return RedirectResponse(url=f"{base_url}/?error=oauth_failed")

    user = await get_or_create_user(user_info)
    token = create_access_token({"sub": user["_id"], "email": user["email"]})

    redirect = RedirectResponse(url=f"{base_url}/?auth_success=1")
    redirect.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=False,
    )
    return redirect


@router.post("/google/verify", response_model=TokenResponse, summary="Verify Google Identity Services credential")
async def verify_google(body: GoogleVerifyRequest, response: Response):
    """Verifies a Google ID token passed directly from client-side Google button / One-Tap."""
    settings = get_settings()
    user_info = await verify_google_credential(body.credential)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not verify Google ID token with Google identity servers.",
        )

    user = await get_or_create_user(user_info)
    token = create_access_token({"sub": user["_id"], "email": user["email"]})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=False,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserPublic(**user),
    )


@router.post("/demo-login", response_model=TokenResponse, summary="Instant Chef or Viewer demo login")
async def demo_login(response: Response, as_editor: bool = Query(default=True, description="Login as authorized editor (True) or viewer (False)")):
    """Instant login for local development and testing permissions without requiring Google OAuth."""
    settings = get_settings()
    if not settings.allow_dev_login:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo login is disabled in this environment.")

    user = await get_demo_user(as_editor=as_editor)
    token = create_access_token({"sub": user["_id"], "email": user["email"]})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=False,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserPublic(**user),
    )


@router.get("/me", response_model=UserPublic, summary="Get current signed-in user profile & permissions")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Returns the authenticated user's profile and permissions (can_edit, role)."""
    return UserPublic(**current_user)


@router.post("/logout", summary="Sign out current user")
async def logout(response: Response):
    """Clears the access_token session cookie."""
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}
