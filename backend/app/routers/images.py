import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.config import get_settings
from app.database import get_database
from app.dependencies.auth import require_editor_user
from app.repositories.image_repository import ImageRepository, image_url
from app.services.image_service import ImageProcessingError, process_image

logger = logging.getLogger("recipe_book.images")

router = APIRouter(prefix="/images", tags=["Images"])

READ_CHUNK_BYTES = 1024 * 1024


class ImageUploadResponse(BaseModel):
    id: str
    url: str
    width: int
    height: int
    size_bytes: int
    original_size_bytes: int


def get_image_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> ImageRepository:
    return ImageRepository(db)


async def read_limited(upload: UploadFile, limit: int) -> bytes:
    """Read the upload, giving up as soon as it passes `limit` bytes."""
    chunks = []
    total = 0
    while chunk := await upload.read(READ_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"Image is too large. The maximum upload size is {limit // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a recipe photo (Authorized Editors Only)",
)
async def upload_image(
    file: UploadFile = File(..., description="JPEG, PNG, WebP or GIF image"),
    images: ImageRepository = Depends(get_image_repository),
    current_user: Dict[str, Any] = Depends(require_editor_user),
):
    """Scale the photo down, re-encode it as WebP and store it. Use the returned `url` in a recipe's `images`."""
    raw = await read_limited(file, get_settings().image_upload_max_bytes)
    if not raw:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    try:
        processed = await run_in_threadpool(process_image, raw)
    except ImageProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    doc = await images.create(processed, original_bytes=len(raw), created_by=str(current_user["_id"]))
    image_id = str(doc["_id"])
    logger.info(
        "Stored uploaded image %s (%dx%d, %d bytes from %d bytes)",
        image_id, processed.width, processed.height, len(processed.data), len(raw),
    )
    return ImageUploadResponse(
        id=image_id,
        url=image_url(image_id),
        width=processed.width,
        height=processed.height,
        size_bytes=len(processed.data),
        original_size_bytes=len(raw),
    )


@router.get("/{image_id}", summary="Fetch an uploaded recipe photo", response_class=Response)
async def get_image(image_id: str, images: ImageRepository = Depends(get_image_repository)):
    doc = await images.get(image_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found.")
    return Response(
        content=bytes(doc["data"]),
        media_type=doc.get("content_type", "image/webp"),
        headers={
            # An id always names the same bytes, so browsers and CDNs may keep it forever
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{image_id}"',
        },
    )
