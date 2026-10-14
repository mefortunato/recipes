from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.database import get_database
from app.dependencies.auth import require_editor_user
from app.models.recipe import (
    RecipeCreate,
    RecipeListResponse,
    RecipeResponse,
    RecipeUpdate,
    ScaledRecipeResponse,
)
from app.services.recipe_service import RecipeService

router = APIRouter(prefix="/recipes", tags=["Recipes"])


def get_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> RecipeService:
    return RecipeService(db)


@router.get("", response_model=RecipeListResponse, summary="List and filter recipes")
async def list_recipes(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=12, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(default=None, description="Search keyword in title, cuisine, ingredients, tags"),
    category: Optional[str] = Query(default=None, description="Category filter (e.g. Main Course, Dessert)"),
    cuisine: Optional[str] = Query(default=None, description="Cuisine filter (e.g. Italian, Mexican)"),
    tag: Optional[str] = Query(default=None, description="Tag filter (e.g. vegetarian, keto)"),
    max_time: Optional[int] = Query(default=None, ge=1, description="Maximum total cooking time in minutes"),
    difficulty: Optional[str] = Query(default=None, description="Difficulty level (Easy, Medium, Hard)"),
    is_favorite: Optional[bool] = Query(default=None, description="Filter favorites"),
    sort_by: str = Query(default="created_at", description="Field to sort by"),
    sort_order: int = Query(default=-1, description="Sort direction: 1 for asc, -1 for desc"),
    service: RecipeService = Depends(get_service),
):
    recipes, total, total_pages = await service.list_recipes(
        page=page,
        page_size=page_size,
        search=search,
        category=category,
        cuisine=cuisine,
        tag=tag,
        max_time=max_time,
        difficulty=difficulty,
        is_favorite=is_favorite,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return RecipeListResponse(
        recipes=recipes,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED, summary="Create a new recipe (Authorized Editors Only)")
async def create_recipe(
    recipe_in: RecipeCreate,
    service: RecipeService = Depends(get_service),
    current_user: Dict[str, Any] = Depends(require_editor_user),
):
    return await service.create_recipe(recipe_in)


@router.get("/meta/tags", response_model=List[str], summary="Get all distinct recipe tags")
async def get_tags(service: RecipeService = Depends(get_service)):
    return await service.get_tags()


@router.get("/meta/cuisines", response_model=List[str], summary="Get all distinct cuisines")
async def get_cuisines(service: RecipeService = Depends(get_service)):
    return await service.get_cuisines()


@router.get("/meta/categories", response_model=List[str], summary="Get all distinct categories")
async def get_categories(service: RecipeService = Depends(get_service)):
    return await service.get_categories()


@router.post("/seed", summary="Seed sample recipes into the database (Authorized Editors Only)")
async def seed_recipes(
    force: bool = Query(default=False, description="Force re-seeding even if recipes already exist"),
    service: RecipeService = Depends(get_service),
    current_user: Dict[str, Any] = Depends(require_editor_user),
):
    count = await service.seed_recipes(force=force)
    return {"message": f"Successfully seeded {count} sample recipes.", "count": count}


@router.get("/{recipe_id}", response_model=RecipeResponse, summary="Get recipe details by ID")
async def get_recipe(
    recipe_id: str,
    service: RecipeService = Depends(get_service),
):
    recipe = await service.get_recipe(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id '{recipe_id}' was not found.",
        )
    return recipe


@router.put("/{recipe_id}", response_model=RecipeResponse, summary="Update an existing recipe (Authorized Editors Only)")
async def update_recipe(
    recipe_id: str,
    recipe_in: RecipeUpdate,
    service: RecipeService = Depends(get_service),
    current_user: Dict[str, Any] = Depends(require_editor_user),
):
    updated = await service.update_recipe(recipe_id, recipe_in)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id '{recipe_id}' was not found or could not be updated.",
        )
    return updated


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a recipe by ID (Authorized Editors Only)")
async def delete_recipe(
    recipe_id: str,
    service: RecipeService = Depends(get_service),
    current_user: Dict[str, Any] = Depends(require_editor_user),
):
    deleted = await service.delete_recipe(recipe_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id '{recipe_id}' was not found.",
        )
    return None


@router.get("/{recipe_id}/scale", response_model=ScaledRecipeResponse, summary="Dynamically scale recipe ingredients for target servings")
async def scale_recipe(
    recipe_id: str,
    servings: int = Query(..., ge=1, le=100, description="Target number of servings"),
    service: RecipeService = Depends(get_service),
):
    scaled = await service.scale_recipe(recipe_id, target_servings=servings)
    if not scaled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe with id '{recipe_id}' was not found.",
        )
    return scaled
