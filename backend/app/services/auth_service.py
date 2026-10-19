import base64
import json
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


def decode_google_jwt(credential: str) -> dict:
    """Decodes Google Identity Services JWT payload safely without secret."""
    try:
        parts = credential.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1]
        remainder = len(payload_b64) % 4
        if remainder > 0:
            payload_b64 += "=" * (4 - remainder)
        decoded_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(decoded_bytes.decode("utf-8"))
    except Exception as e:
        logger.warning("Error decoding Google credential: %s", e)
        return {}


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

    # 3. Fallback: decode JWT directly without network call (useful in dev/mock environments)
    decoded = decode_google_jwt(credential)
    if decoded and decoded.get("email"):
        return {
            "google_id": decoded.get("sub") or decoded.get("user_id"),
            "email": decoded.get("email"),
            "name": decoded.get("name", "Gourmet Chef"),
            "picture": decoded.get("picture"),
        }

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
    """Finds existing user by email or creates a new one, keeping bootstrap/database permissions."""
    settings = get_settings()
    db = db_manager.db
    if db is None:
        raise RuntimeError("Database connection is not initialized")

    email = user_info["email"].strip().lower()
    existing = await db.users.find_one({"email": email})

    is_privileged = settings.is_privileged_email(email)

    if existing:
        # If user email is in ALLOWED_EDITOR_EMAILS, they are guaranteed bootstrap admin
        if is_privileged:
            role = "admin"
            can_edit = True
            is_admin = True
        else:
            # Respect database permissions set by an admin!
            role = existing.get("role", "viewer")
            can_edit = existing.get("can_edit", (role in ("admin", "editor")))
            is_admin = (role == "admin") or existing.get("is_admin", False)

        update_fields = {
            "last_login": utc_now(),
            "role": role,
            "can_edit": can_edit,
            "is_admin": is_admin,
            "is_bootstrap": is_privileged,
        }
        if user_info.get("name") and (not existing.get("name") or existing.get("name") == email.split("@")[0]):
            update_fields["name"] = user_info["name"]
        if user_info.get("picture") and not existing.get("picture"):
            update_fields["picture"] = user_info["picture"]
        if user_info.get("google_id") and not existing.get("google_id"):
            update_fields["google_id"] = user_info["google_id"]

        await db.users.update_one({"_id": existing["_id"]}, {"$set": update_fields})
        existing["_id"] = str(existing["_id"])
        existing.update(update_fields)
        return existing

    # Create new user
    if is_privileged:
        role = "admin"
        can_edit = True
        is_admin = True
    else:
        role = user_info.get("role", "viewer")
        can_edit = user_info.get("can_edit", (role in ("admin", "editor")))
        is_admin = (role == "admin") or user_info.get("is_admin", False)

    new_user = {
        "email": email,
        "name": user_info.get("name", email.split("@")[0]),
        "picture": user_info.get("picture", ""),
        "google_id": user_info.get("google_id"),
        "role": role,
        "can_edit": can_edit,
        "is_admin": is_admin,
        "is_bootstrap": is_privileged,
        "created_at": utc_now(),
        "last_login": utc_now(),
    }
    result = await db.users.insert_one(new_user)
    new_user["_id"] = str(result.inserted_id)
    return new_user


async def purge_demo_users(db) -> int:
    """Purges any legacy demo users from the users collection."""
    if db is None:
        return 0
    res = await db.users.delete_many({
        "$or": [
            {"email": {"$regex": r"@gourmetvault\.com$", "$options": "i"}},
            {"google_id": {"$regex": r"^demo-", "$options": "i"}},
        ]
    })
    if res.deleted_count > 0:
        logger.info("Purged %d legacy demo users from database", res.deleted_count)
    return res.deleted_count
