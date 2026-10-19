import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.recipe import RecipeCreate, RecipeResponse, RecipeUpdate


def doc_to_response(doc: Dict[str, Any], current_user_id: Optional[str] = None) -> RecipeResponse:
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

    upvoted_by = [str(u) for u in doc.get("upvoted_by", [])]
    downvoted_by = [str(u) for u in doc.get("downvoted_by", [])]

    upvotes_count = doc.get("upvotes_count")
    if upvotes_count is None:
        upvotes_count = len(upvoted_by)

    downvotes_count = doc.get("downvotes_count")
    if downvotes_count is None:
        downvotes_count = len(downvoted_by)

    aggregate_rating = doc.get("aggregate_rating")
    if aggregate_rating is None:
        aggregate_rating = upvotes_count - downvotes_count

    user_vote = None
    if current_user_id is not None:
        uid_str = str(current_user_id)
        if uid_str in upvoted_by:
            user_vote = 1
        elif uid_str in downvoted_by:
            user_vote = -1
        else:
            user_vote = 0

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
        upvotes_count=upvotes_count,
        downvotes_count=downvotes_count,
        aggregate_rating=aggregate_rating,
        user_vote=user_vote,
        is_favorite=doc.get("is_favorite", False) or (user_vote == 1),
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
        user_voted: Optional[str] = None,
        current_user_id: Optional[str] = None,
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

        # Handle user-specific vote filtering or legacy favorite filtering
        if user_voted:
            v_clean = user_voted.strip().lower()
            if current_user_id:
                uid_str = str(current_user_id)
                if v_clean in ("up", "1", "upvote"):
                    filters["upvoted_by"] = uid_str
                elif v_clean in ("down", "-1", "downvote"):
                    filters["downvoted_by"] = uid_str
            else:
                # Unauthenticated user cannot have upvoted recipes
                if v_clean in ("up", "1", "upvote", "down", "-1"):
                    filters["_id"] = None
        elif is_favorite is not None:
            if current_user_id:
                uid_str = str(current_user_id)
                if is_favorite:
                    filters["$or"] = [{"is_favorite": True}, {"upvoted_by": uid_str}]
                else:
                    filters["is_favorite"] = False
            else:
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
        user_voted: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: int = -1,
        current_user_id: Optional[str] = None,
    ) -> Tuple[List[RecipeResponse], int]:
        query = self._build_filter(
            search=search,
            category=category,
            cuisine=cuisine,
            tag=tag,
            max_time=max_time,
            difficulty=difficulty,
            is_favorite=is_favorite,
            user_voted=user_voted,
            current_user_id=current_user_id,
        )

        total = await self.collection.count_documents(query)

        # Allowed sorting fields
        valid_sort_fields = {
            "created_at": "created_at",
            "title": "title",
            "prep_time_minutes": "prep_time_minutes",
            "cook_time_minutes": "cook_time_minutes",
            "servings": "servings",
            "aggregate_rating": "aggregate_rating",
            "rating": "aggregate_rating",
            "upvotes_count": "upvotes_count",
            "downvotes_count": "downvotes_count",
        }
        target_field = valid_sort_fields.get(sort_by, "created_at")

        if target_field in ("aggregate_rating", "upvotes_count"):
            sort_criteria = [(target_field, sort_order), ("created_at", -1)]
        else:
            sort_criteria = [(target_field, sort_order)]

        cursor = self.collection.find(query).sort(sort_criteria).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        recipes = [doc_to_response(doc, current_user_id=current_user_id) for doc in docs]
        return recipes, total

    async def get_by_id(self, recipe_id: str, current_user_id: Optional[str] = None) -> Optional[RecipeResponse]:
        try:
            obj_id = ObjectId(recipe_id)
        except InvalidId:
            return None

        doc = await self.collection.find_one({"_id": obj_id})
        if not doc:
            return None
        return doc_to_response(doc, current_user_id=current_user_id)

    async def create(self, recipe_in: RecipeCreate, current_user_id: Optional[str] = None) -> RecipeResponse:
        now = datetime.now(timezone.utc)
        doc = recipe_in.model_dump()
        doc["created_at"] = now
        doc["updated_at"] = now
        doc["upvoted_by"] = doc.get("upvoted_by") or []
        doc["downvoted_by"] = doc.get("downvoted_by") or []
        doc["upvotes_count"] = doc.get("upvotes_count", len(doc["upvoted_by"]))
        doc["downvotes_count"] = doc.get("downvotes_count", len(doc["downvoted_by"]))
        doc["aggregate_rating"] = doc["upvotes_count"] - doc["downvotes_count"]

        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc_to_response(doc, current_user_id=current_user_id)

    async def update(self, recipe_id: str, recipe_in: RecipeUpdate, current_user_id: Optional[str] = None) -> Optional[RecipeResponse]:
        try:
            obj_id = ObjectId(recipe_id)
        except InvalidId:
            return None

        update_data = {k: v for k, v in recipe_in.model_dump(exclude_unset=True).items()}
        if not update_data:
            return await self.get_by_id(recipe_id, current_user_id=current_user_id)

        update_data["updated_at"] = datetime.now(timezone.utc)

        result = await self.collection.find_one_and_update(
            {"_id": obj_id},
            {"$set": update_data},
            return_document=True,
        )

        if not result:
            return None
        return doc_to_response(result, current_user_id=current_user_id)

    async def vote(
        self,
        recipe_id: str,
        user_id: str,
        vote_val: int,
        toggle: bool = False,
    ) -> Optional[RecipeResponse]:
        """User vote: 1 for upvote, -1 for downvote, 0 for clear.
        If toggle is True and user already voted the same way, the vote is cleared.
        """
        try:
            obj_id = ObjectId(recipe_id)
        except InvalidId:
            return None

        doc = await self.collection.find_one({"_id": obj_id})
        if not doc:
            return None

        uid_str = str(user_id)
        upvoted_by = [str(u) for u in doc.get("upvoted_by", [])]
        downvoted_by = [str(u) for u in doc.get("downvoted_by", [])]

        orig_up_count = doc.get("upvotes_count")
        if orig_up_count is None:
            orig_up_count = len(upvoted_by)

        orig_down_count = doc.get("downvotes_count")
        if orig_down_count is None:
            orig_down_count = len(downvoted_by)

        current_vote = 1 if uid_str in upvoted_by else (-1 if uid_str in downvoted_by else 0)

        up_delta = 0
        down_delta = 0

        if vote_val == 1:
            if current_vote == 1 and toggle:
                # Toggle off upvote
                upvoted_by = [u for u in upvoted_by if u != uid_str]
                up_delta -= 1
            elif current_vote == 1:
                # Already upvoted, no change
                pass
            else:
                if uid_str in downvoted_by:
                    downvoted_by = [u for u in downvoted_by if u != uid_str]
                    down_delta -= 1
                if uid_str not in upvoted_by:
                    upvoted_by.append(uid_str)
                    up_delta += 1
        elif vote_val == -1:
            if current_vote == -1 and toggle:
                # Toggle off downvote
                downvoted_by = [u for u in downvoted_by if u != uid_str]
                down_delta -= 1
            elif current_vote == -1:
                # Already downvoted, no change
                pass
            else:
                if uid_str in upvoted_by:
                    upvoted_by = [u for u in upvoted_by if u != uid_str]
                    up_delta -= 1
                if uid_str not in downvoted_by:
                    downvoted_by.append(uid_str)
                    down_delta += 1
        elif vote_val == 0:
            if uid_str in upvoted_by:
                upvoted_by = [u for u in upvoted_by if u != uid_str]
                up_delta -= 1
            if uid_str in downvoted_by:
                downvoted_by = [u for u in downvoted_by if u != uid_str]
                down_delta -= 1

        upvotes_count = max(0, orig_up_count + up_delta)
        downvotes_count = max(0, orig_down_count + down_delta)
        upvotes_count = max(upvotes_count, len(upvoted_by))
        downvotes_count = max(downvotes_count, len(downvoted_by))
        aggregate_rating = upvotes_count - downvotes_count

        update_fields = {
            "upvoted_by": upvoted_by,
            "downvoted_by": downvoted_by,
            "upvotes_count": upvotes_count,
            "downvotes_count": downvotes_count,
            "aggregate_rating": aggregate_rating,
            "updated_at": datetime.now(timezone.utc),
        }

        updated_doc = await self.collection.find_one_and_update(
            {"_id": obj_id},
            {"$set": update_fields},
            return_document=True,
        )
        if not updated_doc:
            return None

        return doc_to_response(updated_doc, current_user_id=uid_str)

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

