"""Personal API keys that let AI agents (and scripts) submit recipes on a user's behalf.

A key is shown to its owner once. Only a SHA-256 digest is stored, so a database leak doesn't
hand out working keys. Keys act as their owner, but with a narrower scope than a browser
session: they can read, create and edit recipes and upload photos, never delete recipes,
manage users or mint more keys. The owner's role is checked on every request, so demoting
or deleting the owner disables their keys at once.
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

API_KEYS_COLLECTION = "api_keys"
API_KEY_PREFIX = "rbk_"
MAX_ACTIVE_KEYS_PER_USER = 20
# Only refresh last_used_at this often, so busy agents don't write to the key on every request
LAST_USED_RESOLUTION_SECONDS = 60


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def looks_like_api_key(token: Optional[str]) -> bool:
    return bool(token) and token.startswith(API_KEY_PREFIX)


def generate_api_key() -> str:
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def public_key_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name", ""),
        "prefix": doc.get("prefix", ""),
        "created_at": doc.get("created_at"),
        "last_used_at": doc.get("last_used_at"),
    }


async def create_api_key(db: AsyncIOMotorDatabase, user_id: str, name: str) -> Dict[str, Any]:
    """Create a key and return its public view plus the raw `key` (never retrievable again)."""
    raw_key = generate_api_key()
    doc = {
        "user_id": ObjectId(user_id),
        "name": name,
        # Enough of the key to recognise it in a list, not enough to use it
        "prefix": raw_key[: len(API_KEY_PREFIX) + 6],
        "key_hash": hash_api_key(raw_key),
        "created_at": utc_now(),
        "last_used_at": None,
    }
    result = await db[API_KEYS_COLLECTION].insert_one(doc)
    doc["_id"] = result.inserted_id
    return {**public_key_view(doc), "key": raw_key}


async def count_api_keys(db: AsyncIOMotorDatabase, user_id: str) -> int:
    return await db[API_KEYS_COLLECTION].count_documents({"user_id": ObjectId(user_id)})


async def list_api_keys(db: AsyncIOMotorDatabase, user_id: str) -> List[Dict[str, Any]]:
    cursor = db[API_KEYS_COLLECTION].find({"user_id": ObjectId(user_id)}).sort("created_at", -1)
    return [public_key_view(doc) async for doc in cursor]


async def revoke_api_key(db: AsyncIOMotorDatabase, user_id: str, key_id: str) -> bool:
    try:
        oid = ObjectId(key_id)
    except Exception:
        return False
    result = await db[API_KEYS_COLLECTION].delete_one({"_id": oid, "user_id": ObjectId(user_id)})
    return result.deleted_count == 1


async def revoke_all_api_keys(db: AsyncIOMotorDatabase, user_id: Any) -> None:
    await db[API_KEYS_COLLECTION].delete_many({"user_id": ObjectId(str(user_id))})


async def find_api_key(db: AsyncIOMotorDatabase, raw_key: str) -> Optional[Dict[str, Any]]:
    """Look up a presented key; refreshes its last_used_at timestamp."""
    doc = await db[API_KEYS_COLLECTION].find_one({"key_hash": hash_api_key(raw_key)})
    if not doc:
        return None
    now = utc_now()
    last_used = doc.get("last_used_at")
    if last_used is not None and last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=timezone.utc)
    if last_used is None or (now - last_used).total_seconds() > LAST_USED_RESOLUTION_SECONDS:
        await db[API_KEYS_COLLECTION].update_one({"_id": doc["_id"]}, {"$set": {"last_used_at": now}})
    return doc
