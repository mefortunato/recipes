import logging
import math
from typing import List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.recipe import (
    RecipeCreate,
    RecipeResponse,
    RecipeUpdate,
    ScaledIngredient,
    ScaledRecipeResponse,
)
from app.repositories.recipe_repository import RecipeRepository
from app.seed_data import SAMPLE_RECIPES

logger = logging.getLogger("recipe_book.service")


def round_amount(amount: float) -> float:
    """Format recipe quantity to readable cooking units (e.g. 0.33, 0.5, 1.25)."""
    if amount >= 10:
        return round(amount, 1) if not amount.is_integer() else round(amount)
    return round(amount, 2)


class RecipeService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.repository = RecipeRepository(db)

    async def list_recipes(
        self,
        page: int = 1,
        page_size: int = 12,
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
    ) -> Tuple[List[RecipeResponse], int, int]:
        """Fetch paginated recipes with total count and calculated pages."""
        skip = (max(page, 1) - 1) * page_size
        recipes, total = await self.repository.list_recipes(
            skip=skip,
            limit=page_size,
            search=search,
            category=category,
            cuisine=cuisine,
            tag=tag,
            max_time=max_time,
            difficulty=difficulty,
            is_favorite=is_favorite,
            user_voted=user_voted,
            sort_by=sort_by,
            sort_order=sort_order,
            current_user_id=current_user_id,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return recipes, total, total_pages

    async def get_recipe(self, recipe_id: str, current_user_id: Optional[str] = None) -> Optional[RecipeResponse]:
        return await self.repository.get_by_id(recipe_id, current_user_id=current_user_id)

    async def create_recipe(self, recipe_in: RecipeCreate, current_user_id: Optional[str] = None) -> RecipeResponse:
        return await self.repository.create(recipe_in, current_user_id=current_user_id)

    async def update_recipe(self, recipe_id: str, recipe_in: RecipeUpdate, current_user_id: Optional[str] = None) -> Optional[RecipeResponse]:
        return await self.repository.update(recipe_id, recipe_in, current_user_id=current_user_id)

    async def vote_recipe(
        self,
        recipe_id: str,
        user_id: str,
        vote_val: int,
        toggle: bool = False,
    ) -> Optional[RecipeResponse]:
        return await self.repository.vote(recipe_id, user_id, vote_val, toggle=toggle)

    async def delete_recipe(self, recipe_id: str) -> bool:
        return await self.repository.delete(recipe_id)


    async def scale_recipe(self, recipe_id: str, target_servings: int) -> Optional[ScaledRecipeResponse]:
        recipe = await self.repository.get_by_id(recipe_id)
        if not recipe:
            return None

        if target_servings < 1:
            target_servings = 1

        multiplier = target_servings / recipe.servings

        scaled_ingredients: List[ScaledIngredient] = []
        for ing in recipe.ingredients:
            scaled_amount = round_amount(ing.amount * multiplier)
            scaled_ingredients.append(
                ScaledIngredient(
                    name=ing.name,
                    amount=scaled_amount,
                    unit=ing.unit,
                    notes=ing.notes,
                    original_amount=ing.amount,
                    scaled_amount=scaled_amount,
                )
            )

        return ScaledRecipeResponse(
            id=recipe.id,
            title=recipe.title,
            original_servings=recipe.servings,
            target_servings=target_servings,
            scale_multiplier=round(multiplier, 3),
            ingredients=scaled_ingredients,
        )

    async def get_tags(self) -> List[str]:
        return await self.repository.get_distinct_tags()

    async def get_cuisines(self) -> List[str]:
        return await self.repository.get_distinct_cuisines()

    async def get_categories(self) -> List[str]:
        return await self.repository.get_distinct_categories()

    async def seed_recipes(self, force: bool = False) -> int:
        """Seed sample culinary recipes if the collection is empty or forced, and backfill missing images."""
        total = await self.repository.count_total()
        if total == 0 or force:
            if force and total > 0:
                await self.repository.collection.delete_many({})
            inserted_count = 0
            for sample in SAMPLE_RECIPES:
                await self.repository.create(sample)
                inserted_count += 1
            logger.info("Successfully seeded %d sample recipes.", inserted_count)
            return inserted_count

        # If database already contains recipes, ensure existing sample recipes have their images backfilled
        updated_count = 0
        for sample in SAMPLE_RECIPES:
            existing = await self.repository.collection.find_one({"title": sample.title})
            if existing and (not existing.get("images") or len(existing.get("images", [])) < len(sample.images)):
                await self.repository.collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"images": sample.images, "image_url": sample.image_url}}
                )
                updated_count += 1

        if updated_count > 0:
            logger.info("Backfilled images for %d existing sample recipes.", updated_count)
        else:
            logger.info("Database already contains %d recipes, skipping seed.", total)
        return 0
