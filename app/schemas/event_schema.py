from uuid import UUID

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    event_uuid: UUID | None = None
    project_id: int
    event_type_id: int
    schema_version: str = Field(default="1.0", max_length=30)
    payload: dict


class EventReceived(BaseModel):
    id: int
    event_uuid: UUID
    project_id: int
    event_type_id: int
    schema_version: str
    payload: dict
    status: str

    model_config = {
        "from_attributes": True
    }