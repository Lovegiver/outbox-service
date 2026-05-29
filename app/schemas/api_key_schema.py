from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(
        min_length=3,
        max_length=100,
    )


class ApiKeyCreated(BaseModel):
    id: int
    project_id: int
    name: str
    key_prefix: str
    api_key: str


class ApiKeyRead(BaseModel):
    id: int
    project_id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    revoked_at: datetime | None
    last_used_at: datetime | None

    model_config = {
        "from_attributes": True
    }