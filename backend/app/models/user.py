from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class UserPublic(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id")
    email: str
    name: str
    picture: Optional[str] = None
    role: str = Field(default="viewer", description="'editor' or 'viewer'")
    can_edit: bool = Field(default=False, description="True if user is permitted to create/modify recipes")
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class GoogleVerifyRequest(BaseModel):
    credential: str


class AuthConfigResponse(BaseModel):
    google_client_id: str
    google_auth_enabled: bool
    dev_login_enabled: bool
    allowed_editor_emails: List[str]
