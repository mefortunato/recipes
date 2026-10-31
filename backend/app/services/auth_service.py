import asyncio
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import jwt
import httpx
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.config import Settings, get_settings

logger = logging.getLogger("recipe_book.auth")

ROLES = ("admin", "editor", "viewer")
# Permission flags that older user documents stored alongside 'role'; 'role' is now the only source of truth
LEGACY_PERMISSION_FIELDS = {"can_edit": "", "is_admin": "", "is_bootstrap": ""}
# Collection of individually revoked session token IDs (expired entries are purged by a TTL index)
REVOKED_TOKENS_COLLECTION = "revoked_tokens"


class AccountLinkError(Exception):
    """A Google identity tried to sign in to an account already bound to a different Google identity."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Sign a session token. Each token gets a unique `jti` so it can be revoked on its own."""
    settings = get_settings()
    to_encode = data.copy()
    now = utc_now()
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"iat": now, "exp": expire, "jti": secrets.token_urlsafe(16)})
    to_encode.setdefault("sv", 0)
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_session_token(user: Dict[str, Any]) -> str:
    """Session token bound to the user's current session_version (bumped by 'sign out everywhere')."""
    return create_access_token({
        "sub": str(user["_id"]),
        "email": user["email"],
        "sv": int(user.get("session_version", 0)),
    })


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as e:
        logger.warning("JWT decode failure: %s", e)
        return None


async def revoke_token(db: AsyncIOMotorDatabase, payload: Dict[str, Any]) -> None:
    """Deny-list a single session token until it would have expired anyway."""
    jti = payload.get("jti")
    if not jti:
        return
    expires_at = datetime.fromtimestamp(int(payload.get("exp", 0)), tz=timezone.utc)
    await db[REVOKED_TOKENS_COLLECTION].update_one(
        {"_id": jti},
        {"$set": {"expires_at": expires_at, "sub": payload.get("sub")}},
        upsert=True,
    )


async def is_token_revoked(db: AsyncIOMotorDatabase, payload: Dict[str, Any], user_doc: Dict[str, Any]) -> bool:
    """A token is dead if it was individually revoked or predates the user's latest 'sign out everywhere'."""
    if int(payload.get("sv", 0)) != int(user_doc.get("session_version", 0)):
        return True
    jti = payload.get("jti")
    if not jti:
        # Tokens issued before revocation support can't be revoked individually; reject them
        return True
    return await db[REVOKED_TOKENS_COLLECTION].find_one({"_id": jti}) is not None


async def revoke_all_sessions(db: AsyncIOMotorDatabase, user_id: Any) -> None:
    """Invalidate every outstanding session token for a user."""
    await db.users.update_one({"_id": user_id}, {"$inc": {"session_version": 1}})


def stored_role(user_doc: Dict[str, Any]) -> str:
    """The role persisted for a user, upgrading documents that still carry legacy permission flags."""
    role = user_doc.get("role", "viewer")
    if role not in ROLES:
        role = "viewer"
    if role != "admin" and user_doc.get("is_admin"):
        return "admin"
    if role == "viewer" and user_doc.get("can_edit"):
        return "editor"
    return role


def resolve_permissions(user_doc: Dict[str, Any], settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Fill in a user document's effective role and derived permission flags.

    Bootstrap emails in ALLOWED_EDITOR_EMAILS are always admins; everyone else gets their stored
    role. A '*' in ALLOWED_EDITOR_EMAILS additionally lets every signed-in user edit recipes.
    """
    settings = settings or get_settings()
    is_bootstrap = settings.is_privileged_email(user_doc.get("email"))
    role = "admin" if is_bootstrap else stored_role(user_doc)

    user_doc["_id"] = str(user_doc["_id"])
    user_doc["role"] = role
    user_doc["is_admin"] = role == "admin"
    user_doc["can_edit"] = role in ("admin", "editor") or settings.all_users_can_edit
    user_doc["is_bootstrap"] = is_bootstrap
    return user_doc


async def verify_google_credential(credential: str) -> Optional[Dict[str, Any]]:
    """Verifies a Google ID token from frontend Google Identity Services button.

    The token's signature, audience (our client ID), issuer and expiry must all check out;
    there is deliberately no fallback, since an unverified token can claim any email.
    """
    settings = get_settings()
    if not settings.google_client_id:
        logger.error("GOOGLE_CLIENT_ID is not configured; cannot verify Google credentials.")
        return None

    try:
        idinfo = await asyncio.to_thread(
            id_token.verify_oauth2_token,
            credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception as e:
        logger.warning("Google credential verification failed: %s", e)
        return None

    if not idinfo.get("email") or not idinfo.get("email_verified"):
        logger.warning("Rejected Google credential without a verified email")
        return None

    return {
        "google_id": idinfo.get("sub"),
        "email": idinfo.get("email"),
        "name": idinfo.get("name", "Gourmet Chef"),
        "picture": idinfo.get("picture"),
    }


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
            if not info.get("email") or not info.get("email_verified"):
                logger.warning("Rejected Google profile without a verified email")
                return None
            return {
                "google_id": info.get("sub"),
                "email": info.get("email"),
                "name": info.get("name", "Gourmet Chef"),
                "picture": info.get("picture"),
            }
    except Exception as e:
        logger.error("Exception during Google code exchange: %s", e)
        return None


async def get_or_create_user(db: AsyncIOMotorDatabase, user_info: Dict[str, Any]) -> Dict[str, Any]:
    """Finds existing user by email or creates a new viewer, returning it with resolved permissions."""
    email = user_info["email"].strip().lower()
    existing = await db.users.find_one({"email": email})

    if existing:
        incoming_google_id = user_info.get("google_id")
        if existing.get("google_id") and incoming_google_id and existing["google_id"] != incoming_google_id:
            # Email addresses can be recycled (e.g. a deleted Workspace account recreated for a new
            # person). Don't let a different Google identity inherit the old account and its role.
            logger.warning("Rejected sign-in for %s: Google account ID does not match the linked account", email)
            raise AccountLinkError(email)
        update_fields = {
            "last_login": utc_now(),
            # Persist the role implied by any legacy flags, then drop the flags
            "role": stored_role(existing),
        }
        if user_info.get("name") and (not existing.get("name") or existing.get("name") == email.split("@")[0]):
            update_fields["name"] = user_info["name"]
        if user_info.get("picture") and not existing.get("picture"):
            update_fields["picture"] = user_info["picture"]
        if user_info.get("google_id") and not existing.get("google_id"):
            update_fields["google_id"] = user_info["google_id"]

        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": update_fields, "$unset": LEGACY_PERMISSION_FIELDS},
        )
        existing.update(update_fields)
        for field in LEGACY_PERMISSION_FIELDS:
            existing.pop(field, None)
        return resolve_permissions(existing)

    new_user = {
        "email": email,
        "name": user_info.get("name", email.split("@")[0]),
        "picture": user_info.get("picture", ""),
        "google_id": user_info.get("google_id"),
        "role": "viewer",
        "created_at": utc_now(),
        "last_login": utc_now(),
    }
    try:
        result = await db.users.insert_one(new_user)
    except DuplicateKeyError:
        # A concurrent first sign-in for the same email created the user first
        return await get_or_create_user(db, user_info)
    new_user["_id"] = result.inserted_id
    return resolve_permissions(new_user)
