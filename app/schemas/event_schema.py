from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    project_id: int
    event_type_id: int
    json_version_internal: str = Field(default="1.0", max_length=30)
    payload: dict
    event_uuid: UUID | None = None
    correlation_id: Optional[str] = Field(default=None, max_length=255)
    """
    Optional correlation identifier propagated across multiple
    related events in a distributed workflow or business process.
    """


class EventReceived(BaseModel):
    id: int
    event_uuid: UUID
    project_id: int
    event_type_id: int
    json_version_internal: str
    payload: dict
    status: str
    correlation_id: Optional[str] = None

    model_config = {
        "from_attributes": True
    }