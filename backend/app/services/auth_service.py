import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from bson import ObjectId
from jose import JWTError, jwt
import httpx
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.config import get_settings
from app.database import db_manager

logger = logging.getLogger("recipe_book.auth")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        logger.warning("JWT decode failure: %s", e)
        return None


async def verify_google_credential(credential: str) -> Optional[Dict[str, Any]]:
    """Verifies a Google ID token from frontend Google Identity Services button."""
    settings = get_settings()

    # 1. Attempt official google-auth library verification
    try:
        if settings.google_client_id:
            idinfo = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                settings.google_client_id,
            )
            return {
                "google_id": idinfo.get("sub"),
                "email": idinfo.get("email"),
                "name": idinfo.get("name", "Gourmet Chef"),
                "picture": idinfo.get("picture"),
            }
    except Exception as e:
        logger.warning("Google library verification failed: %s. Trying public tokeninfo endpoint.", e)

    # 2. Fallback to Google's public tokeninfo endpoint
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": credential},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "google_id": data.get("sub"),
                    "email": data.get("email"),
                    "name": data.get("name", "Gourmet Chef"),
                    "picture": data.get("picture"),
                }
    except Exception as ex:
        logger.error("Google tokeninfo fallback failed: %s", ex)

    return None


async def exchange_google_code(code: str, redirect_uri: str) -> Optional[Dict[str, Any]]:
    """Exchanges an authorization code for tokens and fetches user profile."""
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        logger.error("Google OAuth client ID or Secret is not configured.")
        return None

    try:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(token_url, data=data, timeout=10.0)
            if token_resp.status_code != 200:
                logger.error("Token exchange failed: %s", token_resp.text)
                return None
            token_data = token_resp.json()
            access_token = token_data.get("access_token")

            # Fetch Google user profile
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )
            if userinfo_resp.status_code != 200:
                logger.error("Failed to fetch Google userinfo: %s", userinfo_resp.text)
                return None

            info = userinfo_resp.json()
            return {
                "google_id": info.get("sub"),
                "email": info.get("email"),
                "name": info.get("name", "Gourmet Chef"),
                "picture": info.get("picture"),
            }
    except Exception as e:
        logger.error("Exception during Google code exchange: %s", e)
        return None


async def get_or_create_user(user_info: Dict[str, Any]) -> Dict[str, Any]:
    """Finds existing user by email or creates a new one, then calculates editor permission."""
    settings = get_settings()
    db = db_manager.db
    if db is None:
        raise RuntimeError("Database connection is not initialized")

    email = user_info["email"].strip().lower()
    existing = await db.users.find_one({"email": email})

    can_edit = settings.can_user_edit(email)
    role = "editor" if can_edit else "viewer"

    if existing:
        update_fields = {
            "last_login": utc_now(),
            "can_edit": can_edit,
            "role": role,
        }
        if user_info.get("picture") and not existing.get("picture"):
            update_fields["picture"] = user_info["picture"]
        if user_info.get("google_id") and not existing.get("google_id"):
            update_fields["google_id"] = user_info["google_id"]

        await db.users.update_one({"_id": existing["_id"]}, {"$set": update_fields})
        existing["_id"] = str(existing["_id"])
        existing["can_edit"] = can_edit
        existing["role"] = role
        return existing

    # Create new user
    new_user = {
        "email": email,
        "name": user_info.get("name", email.split("@")[0]),
        "picture": user_info.get("picture", ""),
        "google_id": user_info.get("google_id"),
        "role": role,
        "can_edit": can_edit,
        "created_at": utc_now(),
        "last_login": utc_now(),
    }
    result = await db.users.insert_one(new_user)
    new_user["_id"] = str(result.inserted_id)
    return new_user


async def get_demo_user(as_editor: bool = True) -> Dict[str, Any]:
    """Creates or retrieves a demo user for instant test login."""
    if as_editor:
        demo_info = {
            "email": "chef@gourmetvault.com",
            "name": "Head Chef (Editor)",
            "picture": "https://images.unsplash.com/photo-1577219491135-ce391730fb2c?w=150&auto=format&fit=crop&q=80",
            "google_id": "demo-chef-id-001",
        }
    else:
        demo_info = {
            "email": "guest@gourmetvault.com",
            "name": "Guest Foodie (Viewer)",
            "picture": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
            "google_id": "demo-guest-id-002",
        }

    user = await get_or_create_user(demo_info)
    # Ensure demo chef has can_edit true if as_editor was requested
    if as_editor:
        user["can_edit"] = True
        user["role"] = "editor"
    else:
        user["can_edit"] = False
        user["role"] = "viewer"
    return user
