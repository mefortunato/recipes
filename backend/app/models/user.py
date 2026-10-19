from datetime import datetime, timezone
from typing import Optional, List, Any, Dict
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
    email: str
    name: Optional[str] = None
    role: str = Field(default="viewer", description="'admin', 'editor', or 'viewer'")


class UserListResponse(BaseModel):
    users: List[UserPublic]
    total: int
    admin_count: int
    editor_count: int
    viewer_count: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class GoogleVerifyRequest(BaseModel):
    credential: Optional[str] = None
    google_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None


class AuthConfigResponse(BaseModel):
    google_client_id: str
    google_auth_enabled: bool
    dev_login_enabled: bool = False
    allowed_editor_emails: List[str]
