"""Personal API keys and a public guide, so AI agents can submit recipes they co-authored with you."""
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.database import get_database
from app.dependencies.auth import require_session_user
from app.models.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyListResponse
from app.routers.auth import public_base_url
from app.services.api_key_service import (
    MAX_ACTIVE_KEYS_PER_USER,
    count_api_keys,
    create_api_key,
    list_api_keys,
    revoke_api_key,
)

logger = logging.getLogger("recipe_book.agents")

router = APIRouter(tags=["Agent Access"])

AGENT_GUIDE_TEMPLATE = (Path(__file__).resolve().parent.parent / "agent_guide.md").read_text(encoding="utf-8")


@router.get("/auth/api-keys", response_model=ApiKeyListResponse, summary="List your API keys")
async def get_api_keys(
    current_user: Dict[str, Any] = Depends(require_session_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return {"keys": await list_api_keys(db, current_user["_id"])}


@router.post(
    "/auth/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create an API key for an agent (Authorized Editors Only)",
)
async def post_api_key(
    body: ApiKeyCreate,
    current_user: Dict[str, Any] = Depends(require_session_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """The key is returned once. It can create and edit recipes and upload photos as you, nothing more."""
    if not current_user["can_edit"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only editors can create API keys, since keys are for adding recipes.",
        )
    if await count_api_keys(db, current_user["_id"]) >= MAX_ACTIVE_KEYS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have {MAX_ACTIVE_KEYS_PER_USER} API keys. Revoke one you no longer use first.",
        )
    created = await create_api_key(db, current_user["_id"], body.name)
    logger.info("User %s created API key %s (%s)", current_user.get("email"), created["id"], created["prefix"])
    return created


@router.delete("/auth/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke one of your API keys")
async def delete_api_key(
    key_id: str,
    current_user: Dict[str, Any] = Depends(require_session_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    if not await revoke_api_key(db, current_user["_id"], key_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")
    logger.info("User %s revoked API key %s", current_user.get("email"), key_id)
    return None


@router.get("/agents/guide", summary="Instructions for AI agents submitting recipes (Markdown)")
async def agent_guide(request: Request):
    """Public, so you can point an agent at this URL; it contains no secrets."""
    settings = get_settings()
    api_base = f"{public_base_url(request, settings)}{settings.api_prefix}"
    return Response(content=AGENT_GUIDE_TEMPLATE.replace("{{API_BASE}}", api_base), media_type="text/markdown; charset=utf-8")
