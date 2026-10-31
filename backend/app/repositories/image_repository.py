from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from bson import Binary, ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.recipe import UPLOADED_IMAGE_PATH_PREFIX, uploaded_image_id
from app.services.image_service import ProcessedImage


def image_url(image_id: str) -> str:
    return f"{UPLOADED_IMAGE_PATH_PREFIX}{image_id}"


def uploaded_ids(urls: Iterable[Any]) -> List[str]:
    """The ids of uploaded photos among a list of image URLs (external URLs are skipped)."""
    ids = []
    for url in urls or []:
        image_id = uploaded_image_id(str(url))
        if image_id and image_id not in ids:
            ids.append(image_id)
    return ids


class ImageRepository:
    """Uploaded recipe photos, stored as small processed blobs in their own collection.

    Each upload starts out unattached. Saving a recipe that uses it marks it attached; unattached
    uploads (from a form that was abandoned) are removed by a TTL index.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["images"]
        self.recipes = db["recipes"]

    async def create(self, image: ProcessedImage, original_bytes: int, created_by: Optional[str]) -> Dict[str, Any]:
        doc = {
            "data": Binary(image.data),
            "content_type": image.content_type,
            "width": image.width,
            "height": image.height,
            "size_bytes": len(image.data),
            "original_size_bytes": original_bytes,
            "attached": False,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def get(self, image_id: str) -> Optional[Dict[str, Any]]:
        try:
            obj_id = ObjectId(image_id)
        except (InvalidId, TypeError):
            return None
        return await self.collection.find_one({"_id": obj_id})

    async def mark_attached(self, urls: Iterable[Any]) -> None:
        ids = [ObjectId(i) for i in uploaded_ids(urls)]
        if ids:
            await self.collection.update_many({"_id": {"$in": ids}, "attached": False}, {"$set": {"attached": True}})

    async def delete_unreferenced(self, urls: Iterable[Any]) -> int:
        """Delete uploaded photos from `urls` that no recipe uses any more."""
        deleted = 0
        for image_id in uploaded_ids(urls):
            url = image_url(image_id)
            if await self.recipes.count_documents({"$or": [{"images": url}, {"image_url": url}]}, limit=1):
                continue
            result = await self.collection.delete_one({"_id": ObjectId(image_id)})
            deleted += result.deleted_count
        return deleted

    async def delete_all(self) -> None:
        await self.collection.delete_many({})
