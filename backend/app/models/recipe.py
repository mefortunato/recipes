from datetime import datetime
from typing import Annotated, List, Optional, Literal, Union
import re
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator, model_validator
from app.config import get_settings

# Size limits keep a single editor (or a stolen editor session) from storing megabytes per recipe
MAX_TAGS = 30
MAX_TAG_LENGTH = 40
MAX_IMAGES = 10
MAX_URL_LENGTH = 2048
MAX_INGREDIENTS = 100
MAX_INSTRUCTIONS = 100
MAX_MINUTES = 60 * 24 * 7


# Photos uploaded through the API are served from this app, so recipes reference them by path
UPLOADED_IMAGE_PATH_PREFIX = f"{get_settings().api_prefix}/images/"
UPLOADED_IMAGE_PATH_RE = re.compile("^" + re.escape(UPLOADED_IMAGE_PATH_PREFIX) + r"([0-9a-f]{24})$")


def uploaded_image_id(url: str) -> Optional[str]:
    """Return the stored image id when the URL points at an uploaded photo, else None."""
    match = UPLOADED_IMAGE_PATH_RE.match(url or "")
    return match.group(1) if match else None


def validate_image_url(url: str) -> str:
    """Absolute http(s) URLs or our own uploaded-image paths: rejects javascript:, data:, file:,
    protocol-relative values and any other relative path."""
    url = url.strip()
    if uploaded_image_id(url):
        return url
    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"Image URLs must be at most {MAX_URL_LENGTH} characters.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Image URLs must be absolute http:// or https:// URLs, or uploaded photos.")
    if any(ch.isspace() for ch in url) or any(ord(ch) < 32 for ch in url):
        raise ValueError("Image URLs must not contain whitespace or control characters.")
    return url


def clean_tag_list(v):
    if isinstance(v, list):
        tags = [str(tag).strip().lower() for tag in v if str(tag).strip()]
        # De-duplicate while keeping order
        return list(dict.fromkeys(tags))
    return v


def clean_image_list(v):
    if isinstance(v, list):
        images = [str(img).strip() for img in v if str(img).strip()]
    elif isinstance(v, str) and v.strip():
        images = [v.strip()]
    else:
        return []
    return [validate_image_url(img) for img in images]


class Ingredient(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Ingredient name (e.g., 'All-purpose flour')")
    amount: float = Field(..., gt=0, le=1_000_000, description="Quantity")
    unit: str = Field(default="", max_length=30, description="Unit of measurement (e.g., 'cups', 'g', 'tbsp', 'cloves')")
    notes: Optional[str] = Field(default=None, max_length=300, description="Preparation notes, e.g., 'finely chopped'")


class ScaledIngredient(Ingredient):
    original_amount: float = Field(..., description="Amount prior to scaling")
    scaled_amount: float = Field(..., description="Calculated amount for target servings")


class InstructionStep(BaseModel):
    step_number: int = Field(..., ge=1, le=MAX_INSTRUCTIONS, description="Sequential step number")
    instruction: str = Field(..., min_length=2, max_length=2000, description="Actionable instruction text")
    tip: Optional[str] = Field(default=None, max_length=1000, description="Pro-tip or troubleshooting guidance")


class RecipeBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=150, description="Recipe title")
    description: str = Field(..., max_length=1000, description="Short summary or teaser")
    prep_time_minutes: int = Field(default=15, ge=0, le=MAX_MINUTES, description="Hands-on prep time in minutes")
    cook_time_minutes: int = Field(default=30, ge=0, le=MAX_MINUTES, description="Cook or baking time in minutes")
    servings: int = Field(default=4, ge=1, le=100, description="Number of standard portions")
    difficulty: Literal["Easy", "Medium", "Hard"] = Field(default="Medium")
    cuisine: str = Field(default="International", max_length=50, description="Cuisine type, e.g., 'Italian'")
    category: str = Field(default="Main Course", max_length=50, description="Meal category, e.g., 'Dessert'")
    tags: List[Annotated[str, Field(max_length=MAX_TAG_LENGTH)]] = Field(
        default_factory=list, max_length=MAX_TAGS, description="Tags like 'vegetarian', 'quick', 'gluten-free'"
    )
    ingredients: List[Ingredient] = Field(default_factory=list, max_length=MAX_INGREDIENTS, description="List of required ingredients")
    instructions: List[InstructionStep] = Field(default_factory=list, max_length=MAX_INSTRUCTIONS, description="Step-by-step cooking directions")
    images: List[str] = Field(default_factory=list, max_length=MAX_IMAGES, description="List of image URLs for the recipe")
    image_url: Optional[str] = Field(default=None, description="Primary/cover image URL")
    notes: Optional[str] = Field(default=None, max_length=5000, description="Chef's notes, pairings, or personal tweaks")

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        return clean_tag_list(v)

    @field_validator("images", mode="before")
    @classmethod
    def clean_images(cls, v):
        return clean_image_list(v)

    @field_validator("image_url", mode="before")
    @classmethod
    def clean_image_url(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return validate_image_url(str(v))

    @model_validator(mode="after")
    def sync_images(self):
        if not self.image_url and self.images:
            self.image_url = self.images[0]
        elif self.image_url and self.image_url not in self.images:
            self.images.insert(0, self.image_url)
        return self


class RecipeCreate(RecipeBase):
    pass


class SeedRecipe(RecipeCreate):
    """Sample recipe with baseline vote counts. Used for seed data only, never accepted from clients."""
    upvotes_count: int = Field(default=0, ge=0)
    downvotes_count: int = Field(default=0, ge=0)


class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    prep_time_minutes: Optional[int] = Field(default=None, ge=0, le=MAX_MINUTES)
    cook_time_minutes: Optional[int] = Field(default=None, ge=0, le=MAX_MINUTES)
    servings: Optional[int] = Field(default=None, ge=1, le=100)
    difficulty: Optional[Literal["Easy", "Medium", "Hard"]] = None
    cuisine: Optional[str] = Field(default=None, max_length=50)
    category: Optional[str] = Field(default=None, max_length=50)
    tags: Optional[List[Annotated[str, Field(max_length=MAX_TAG_LENGTH)]]] = Field(default=None, max_length=MAX_TAGS)
    ingredients: Optional[List[Ingredient]] = Field(default=None, max_length=MAX_INGREDIENTS)
    instructions: Optional[List[InstructionStep]] = Field(default=None, max_length=MAX_INSTRUCTIONS)
    images: Optional[List[str]] = Field(default=None, max_length=MAX_IMAGES)
    image_url: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("tags", mode="before")
    @classmethod
    def clean_tags(cls, v):
        return clean_tag_list(v)

    @field_validator("images", mode="before")
    @classmethod
    def clean_images(cls, v):
        if v is None:
            return None
        return clean_image_list(v)

    @field_validator("image_url", mode="before")
    @classmethod
    def clean_image_url(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return ""
        return validate_image_url(str(v))

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
    upvotes_count: int = Field(default=0, ge=0, description="Total number of users who upvoted")
    downvotes_count: int = Field(default=0, ge=0, description="Total number of users who downvoted")
    aggregate_rating: int = Field(default=0, description="Aggregate vote rating (upvotes - downvotes)")
    is_favorite: bool = Field(default=False, description="True if the current user upvoted the recipe")
    user_vote: Optional[int] = Field(default=None, description="Current user vote (1 for upvote, -1 for downvote, None/0 for none)")
    created_by: Optional[str] = Field(default=None, description="ID of the user who created the recipe")
    updated_by: Optional[str] = Field(default=None, description="ID of the user who last edited the recipe")


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

