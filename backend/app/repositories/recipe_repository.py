import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.recipe import RecipeCreate, RecipeResponse, RecipeUpdate


def doc_to_response(doc: Dict[str, Any]) -> RecipeResponse:
    """Transform a raw MongoDB document into a typed RecipeResponse model."""
    doc_id = str(doc.get("_id"))
    prep = doc.get("prep_time_minutes", 0)
    cook = doc.get("cook_time_minutes", 0)
    total_time = prep + cook

    created_at = doc.get("created_at") or datetime.now(timezone.utc)
    updated_at = doc.get("updated_at") or created_at

    raw_images = doc.get("images") or []
    image_url = doc.get("image_url")
    if not raw_images and image_url:
        raw_images = [image_url]
    elif raw_images and not image_url:
        image_url = raw_images[0]

    return RecipeResponse(
        id=doc_id,
        title=doc.get("title", ""),
        description=doc.get("description", ""),
        prep_time_minutes=prep,
        cook_time_minutes=cook,
        total_time_minutes=total_time,
        servings=doc.get("servings", 4),
        difficulty=doc.get("difficulty", "Medium"),
        cuisine=doc.get("cuisine", "International"),
        category=doc.get("category", "Main Course"),
        tags=doc.get("tags", []),
        ingredients=doc.get("ingredients", []),
        instructions=doc.get("instructions", []),
        images=raw_images,
        image_url=image_url,
        is_favorite=doc.get("is_favorite", False),
        notes=doc.get("notes"),
        created_at=created_at,
        updated_at=updated_at,
    )


class RecipeRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["recipes"]

    def _build_filter(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        cuisine: Optional[str] = None,
        tag: Optional[str] = None,
        max_time: Optional[int] = None,
        difficulty: Optional[str] = None,
        is_favorite: Optional[bool] = None,
    ) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}

        if search:
            escaped = re.escape(search)
            filters["$or"] = [
                {"title": {"$regex": escaped, "$options": "i"}},
                {"description": {"$regex": escaped, "$options": "i"}},
                {"cuisine": {"$regex": escaped, "$options": "i"}},
                {"ingredients.name": {"$regex": escaped, "$options": "i"}},
                {"tags": {"$regex": escaped, "$options": "i"}},
            ]

        if category and category.lower() != "all":
            filters["category"] = {"$regex": f"^{re.escape(category)}$", "$options": "i"}

        if cuisine and cuisine.lower() != "all":
            filters["cuisine"] = {"$regex": f"^{re.escape(cuisine)}$", "$options": "i"}

        if tag:
            filters["tags"] = tag.strip().lower()

        if difficulty and difficulty.lower() != "all":
            filters["difficulty"] = difficulty

        if is_favorite is not None:
            filters["is_favorite"] = is_favorite

        if max_time and max_time > 0:
            filters["$expr"] = {
                "$lte": [
                    {"$add": ["$prep_time_minutes", "$cook_time_minutes"]},
                    max_time,
                ]
            }

        return filters

    async def list_recipes(
        self,
        skip: int = 0,
        limit: int = 12,
        search: Optional[str] = None,
        category: Optional[str] = None,
        cuisine: Optional[str] = None,
        tag: Optional[str] = None,
        max_time: Optional[int] = None,
        difficulty: Optional[str] = None,
        is_favorite: Optional[bool] = None,
        sort_by: str = "created_at",
        sort_order: int = -1,
    ) -> Tuple[List[RecipeResponse], int]:
        query = self._build_filter(
            search=search,
            category=category,
            cuisine=cuisine,
            tag=tag,
            max_time=max_time,
            difficulty=difficulty,
            is_favorite=is_favorite,
        )

        total = await self.collection.count_documents(query)

        # Allowed sorting fields
        valid_sort_fields = {"created_at", "title", "prep_time_minutes", "cook_time_minutes", "servings"}
        sort_field = sort_by if sort_by in valid_sort_fields else "created_at"

        cursor = self.collection.find(query).sort(sort_field, sort_order).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        recipes = [doc_to_response(doc) for doc in docs]
        return recipes, total

    async def get_by_id(self, recipe_id: str) -> Optional[RecipeResponse]:
        try:
            obj_id = ObjectId(recipe_id)
        except InvalidId:
            return None

        doc = await self.collection.find_one({"_id": obj_id})
        if not doc:
            return None
        return doc_to_response(doc)

    async def create(self, recipe_in: RecipeCreate) -> RecipeResponse:
        now = datetime.now(timezone.utc)
        doc = recipe_in.model_dump()
        doc["created_at"] = now
        doc["updated_at"] = now

        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc_to_response(doc)

    async def update(self, recipe_id: str, recipe_in: RecipeUpdate) -> Optional[RecipeResponse]:
        try:
            obj_id = ObjectId(recipe_id)
        except InvalidId:
            return None

        update_data = {k: v for k, v in recipe_in.model_dump(exclude_unset=True).items()}
        if not update_data:
            return await self.get_by_id(recipe_id)

        update_data["updated_at"] = datetime.now(timezone.utc)

        result = await self.collection.find_one_and_update(
            {"_id": obj_id},
            {"$set": update_data},
            return_document=True,
        )

        if not result:
            return None
        return doc_to_response(result)

    async def delete(self, recipe_id: str) -> bool:
        try:
            obj_id = ObjectId(recipe_id)
        except InvalidId:
            return False

        result = await self.collection.delete_one({"_id": obj_id})
        return result.deleted_count > 0

    async def count_total(self) -> int:
        return await self.collection.count_documents({})

    async def get_distinct_tags(self) -> List[str]:
        tags = await self.collection.distinct("tags")
        return sorted([t for t in tags if t])

    async def get_distinct_cuisines(self) -> List[str]:
        cuisines = await self.collection.distinct("cuisine")
        return sorted([c for c in cuisines if c])

    async def get_distinct_categories(self) -> List[str]:
        categories = await self.collection.distinct("category")
        return sorted([c for c in categories if c])
