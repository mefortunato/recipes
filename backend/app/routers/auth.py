import logging
import secrets
import urllib.parse
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.database import get_database
from app.models.user import UserPublic, TokenResponse, GoogleVerifyRequest, AuthConfigResponse
from app.services.auth_service import (
    create_access_token,
    verify_google_credential,
    exchange_google_code,
    get_or_create_user,
)
from app.dependencies.auth import get_current_user

logger = logging.getLogger("recipe_book.auth")

router = APIRouter(prefix="/auth", tags=["Authentication & Access Control"])

SESSION_COOKIE = "access_token"
OAUTH_STATE_COOKIE = "oauth_state"
OAUTH_STATE_MAX_AGE_SECONDS = 600


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=settings.cookie_secure,
    )


def public_base_url(request: Request, settings: Settings) -> str:
    return settings.frontend_url.rstrip("/") if settings.frontend_url else str(request.base_url).rstrip("/")


def oauth_callback_url(request: Request, settings: Settings) -> str:
    return f"{public_base_url(request, settings)}{settings.api_prefix}/auth/google/callback"


@router.get("/config", response_model=AuthConfigResponse, summary="Get public authentication settings")
async def get_auth_config():
    """Returns public authentication parameters (e.g. Google Client ID)."""
    settings = get_settings()
    return AuthConfigResponse(
        google_client_id=settings.google_client_id or "",
        google_auth_enabled=bool(settings.google_client_id),
        dev_login_enabled=bool(settings.dev_login_enabled),
    )


@router.get("/google/login", summary="Redirect to Google OAuth consent screen")
async def google_login(request: Request):
    """Generates the Google OAuth 2.0 authorization URL and redirects the browser."""
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GOOGLE_CLIENT_ID is not configured in .env.",
        )

    base_url = public_base_url(request, settings)
    if not settings.google_client_secret:
        # If client secret is not configured, redirect to client-side Google Identity Services
        return RedirectResponse(url=f"{base_url}/?open_auth=1")

    # Random state bound to this browser via a short-lived cookie, checked in the callback (login CSRF protection)
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": oauth_callback_url(request, settings),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    }
    redirect = RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}")
    redirect.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        max_age=OAUTH_STATE_MAX_AGE_SECONDS,
        samesite="lax",
        secure=settings.cookie_secure,
        path=f"{settings.api_prefix}/auth/google",
    )
    return redirect


@router.get("/google/callback", summary="Google OAuth authorization code callback")
async def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Exchanges Google authorization code for credentials, creates or updates the user, and sets session cookie."""
    settings = get_settings()
    base_url = public_base_url(request, settings)
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)

    user_info = None
    if error:
        logger.info("Google OAuth returned error: %s", error)
    elif not code or not state or not expected_state or not secrets.compare_digest(state, expected_state):
        logger.warning("Rejected Google OAuth callback with missing or mismatched state")
    else:
        user_info = await exchange_google_code(code, oauth_callback_url(request, settings))

    if not user_info:
        redirect = RedirectResponse(url=f"{base_url}/?error=oauth_failed")
    else:
        user = await get_or_create_user(db, user_info)
        token = create_access_token({"sub": user["_id"], "email": user["email"]})
        redirect = RedirectResponse(url=f"{base_url}/?auth_success=1")
        set_session_cookie(redirect, token, settings)

    redirect.delete_cookie(OAUTH_STATE_COOKIE, path=f"{settings.api_prefix}/auth/google")
    return redirect


@router.post("/google/verify", response_model=TokenResponse, summary="Verify Google Identity Services credential")
async def verify_google(
    body: GoogleVerifyRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Verifies a Google ID token passed directly from client-side Google button / One-Tap."""
    settings = get_settings()
    user_info = None

    if body.credential:
        user_info = await verify_google_credential(body.credential)
    elif settings.dev_login_enabled and body.email:
        user_info = {
            "google_id": body.google_id or f"dev_{body.email.replace('@', '_').replace('.', '_')}",
            "email": body.email,
            "name": body.name or body.email.split("@")[0].capitalize(),
            "picture": body.picture or f"https://api.dicebear.com/7.x/bottts/svg?seed={body.name or body.email}",
        }

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not verify Google ID token with Google identity servers.",
        )

    user = await get_or_create_user(db, user_info)
    token = create_access_token({"sub": user["_id"], "email": user["email"]})
    set_session_cookie(response, token, settings)

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
    settings = get_settings()
    response.delete_cookie(key=SESSION_COOKIE, httponly=True, samesite="lax", secure=settings.cookie_secure)
    return {"message": "Logged out successfully"}
