from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, description="A label to recognise the key, e.g. 'Claude recipe co-author'")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Give the key a name.")
        return v


class ApiKeyPublic(BaseModel):
    id: str
    name: str
    prefix: str = Field(..., description="First characters of the key, to tell keys apart")
    created_at: datetime
    last_used_at: Optional[datetime] = None


class ApiKeyCreated(ApiKeyPublic):
    key: str = Field(..., description="The secret key. Shown only once; store it somewhere safe.")


class ApiKeyListResponse(BaseModel):
    keys: List[ApiKeyPublic]
