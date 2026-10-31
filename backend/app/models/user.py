from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


class UserPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default="")
    email: str
    name: str
    picture: Optional[str] = None
    role: str = Field(default="viewer", description="'admin', 'editor', or 'viewer'")
    can_edit: bool = Field(default=False, description="True if user is permitted to create/modify recipes")
    is_admin: bool = Field(default=False, description="True if user has admin privileges")
    is_bootstrap: bool = Field(default=False, description="True if user is configured via ALLOWED_EDITOR_EMAILS in .env")
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def populate_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            raw_id = data.get("id") or data.get("_id")
            if raw_id is not None:
                data["id"] = str(raw_id)
                data["_id"] = str(raw_id)
        return data


class UserPermissionUpdate(BaseModel):
    role: Optional[str] = Field(default=None, description="'admin', 'editor', or 'viewer'")
    can_edit: Optional[bool] = Field(default=None, description="Direct toggle for recipe editing permissions")


class UserCreateRequest(BaseModel):
    email: str = Field(..., max_length=254)
    name: Optional[str] = Field(default=None, max_length=100)
    role: str = Field(default="viewer", description="'admin', 'editor', or 'viewer'")


class UserListResponse(BaseModel):
    users: List[UserPublic]
    total: int
    admin_count: int
    editor_count: int
    viewer_count: int


class TokenResponse(BaseModel):
    access_token: Optional[str] = Field(default=None, description="Only returned when include_token=true (API clients)")
    token_type: str = "bearer"
    user: UserPublic


class GoogleVerifyRequest(BaseModel):
    credential: Optional[str] = Field(default=None, max_length=4096)
    # Dev-login only fields (ignored unless DEV_LOGIN_ENABLED in a local environment)
    google_id: Optional[str] = Field(default=None, max_length=128)
    email: Optional[str] = Field(default=None, max_length=254)
    name: Optional[str] = Field(default=None, max_length=100)
    picture: Optional[str] = Field(default=None, max_length=2048)
    include_token: bool = Field(default=False, description="Also return the session token in the body (for non-browser API clients)")


class AuthConfigResponse(BaseModel):
    google_client_id: str
    google_auth_enabled: bool
    dev_login_enabled: bool = False
