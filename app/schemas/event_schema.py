from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    project: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    schema_version: str = "1.0"
    payload: dict[str, Any]


class EventReceived(BaseModel):
    status: str
    event: EventIn