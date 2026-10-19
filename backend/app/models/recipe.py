from datetime import datetime, timezone
from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class Ingredient(BaseModel):
    name: str = Field(..., min_length=1, description="Ingredient name (e.g., 'All-purpose flour')")
    amount: float = Field(..., gt=0, description="Quantity")
    unit: str = Field(default="", description="Unit of measurement (e.g., 'cups', 'g', 'tbsp', 'cloves')")
    notes: Optional[str] = Field(default=None, description="Preparation notes, e.g., 'finely chopped'")


class ScaledIngredient(Ingredient):
    original_amount: float = Field(..., description="Amount prior to scaling")
    scaled_amount: float = Field(..., description="Calculated amount for target servings")


class InstructionStep(BaseModel):
    step_number: int = Field(..., ge=1, description="Sequential step number")
    instruction: str = Field(..., min_length=2, description="Actionable instruction text")
    tip: Optional[str] = Field(default=None, description="Pro-tip or troubleshooting guidance")


class RecipeBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=150, description="Recipe title")
    description: str = Field(..., max_length=1000, description="Short summary or teaser")
    prep_time_minutes: int = Field(default=15, ge=0, description="Hands-on prep time in minutes")
    cook_time_minutes: int = Field(default=30, ge=0, description="Cook or baking time in minutes")
    servings: int = Field(default=4, ge=1, le=100, description="Number of standard portions")
    difficulty: Literal["Easy", "Medium", "Hard"] = Field(default="Medium")
    cuisine: str = Field(default="International", max_length=50, description="Cuisine type, e.g., 'Italian'")
    category: str = Field(default="Main Course", max_length=50, description="Meal category, e.g., 'Dessert'")
    tags: List[str] = Field(default_factory=list, description="Tags like 'vegetarian', 'quick', 'gluten-free'")
    ingredients: List[Ingredient] = Field(default_factory=list, description="List of required ingredients")
    instructions: List[InstructionStep] = Field(default_factory=list, description="Step-by-step cooking directions")
    images: List[str] = Field(default_factory=list, description="List of image URLs for the recipe")
    image_url: Optional[str] = Field(default=None, description="Primary/cover image URL")
    upvotes_count: int = Field(default=0, ge=0, description="Total number of users who upvoted")
    downvotes_count: int = Field(default=0, ge=0, description="Total number of users who downvoted")
    aggregate_rating: int = Field(default=0, description="Aggregate vote rating (upvotes - downvotes)")
    is_favorite: Optional[bool] = Field(default=False, description="Legacy bookmarked favorite")
    notes: Optional[str] = Field(default=None, description="Chef's notes, pairings, or personal tweaks")

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if isinstance(v, list):
            return [str(tag).strip().lower() for tag in v if str(tag).strip()]
        return v

    @field_validator("images", mode="before")
    @classmethod
    def clean_images(cls, v):
        if isinstance(v, list):
            return [str(img).strip() for img in v if str(img).strip()]
        elif isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    @model_validator(mode="after")
    def sync_images(self):
        if not self.image_url and self.images:
            self.image_url = self.images[0]
        elif self.image_url and self.image_url not in self.images:
            self.images.insert(0, self.image_url)
        return self


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    prep_time_minutes: Optional[int] = Field(default=None, ge=0)
    cook_time_minutes: Optional[int] = Field(default=None, ge=0)
    servings: Optional[int] = Field(default=None, ge=1, le=100)
    difficulty: Optional[Literal["Easy", "Medium", "Hard"]] = None
    cuisine: Optional[str] = Field(default=None, max_length=50)
    category: Optional[str] = Field(default=None, max_length=50)
    tags: Optional[List[str]] = None
    ingredients: Optional[List[Ingredient]] = None
    instructions: Optional[List[InstructionStep]] = None
    images: Optional[List[str]] = None
    image_url: Optional[str] = None
    is_favorite: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        if isinstance(v, list):
            return [str(tag).strip().lower() for tag in v if str(tag).strip()]
        return v

    @field_validator("images", mode="before")
    @classmethod
    def clean_images(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            return [str(img).strip() for img in v if str(img).strip()]
        elif isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    @model_validator(mode="after")
    def sync_images(self):
        if self.images is not None:
            if not self.image_url and self.images:
                self.image_url = self.images[0]
            elif self.images and self.image_url and self.image_url not in self.images:
                self.images.insert(0, self.image_url)
            elif not self.images and not self.image_url:
                self.image_url = None
        elif self.image_url is not None and self.images is None:
            self.images = [self.image_url] if self.image_url else []
        return self


class RecipeResponse(RecipeBase):
    id: str = Field(..., description="Unique recipe identifier (MongoDB ObjectId string)")
    total_time_minutes: int = Field(..., description="Total duration (prep + cook)")
    created_at: datetime = Field(..., description="Creation timestamp UTC")
    updated_at: datetime = Field(..., description="Last update timestamp UTC")
    user_vote: Optional[int] = Field(default=None, description="Current user vote (1 for upvote, -1 for downvote, None/0 for none)")


class ScaledRecipeResponse(BaseModel):
    id: str
    title: str
    original_servings: int
    target_servings: int
    scale_multiplier: float
    ingredients: List[ScaledIngredient]


class RecipeListResponse(BaseModel):
    recipes: List[RecipeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class VoteRequest(BaseModel):
    vote: Union[int, str] = Field(..., description="1/'up' for upvote, -1/'down' for downvote, 0/'clear' to remove vote")
    toggle: bool = Field(default=False, description="If True, repeat vote will toggle off")

    @field_validator("vote")
    @classmethod
    def validate_vote(cls, v):
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("1", "+1", "up", "upvote", "like", "toggle_up"):
                return 1
            elif v_clean in ("-1", "down", "downvote", "dislike", "toggle_down"):
                return -1
            elif v_clean in ("0", "clear", "none", "remove"):
                return 0
            raise ValueError("Invalid vote string. Must be 'up', 'down', or 'clear'.")
        if isinstance(v, int):
            if v in (1, -1, 0):
                return v
            raise ValueError("Vote integer must be 1, -1, or 0.")
        raise ValueError("Vote must be an integer (1, -1, 0) or string ('up', 'down', 'clear').")


class VoteResponse(BaseModel):
    id: str
    upvotes_count: int
    downvotes_count: int
    aggregate_rating: int
    user_vote: Optional[int]
    message: str

