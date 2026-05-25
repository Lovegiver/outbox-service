from uuid import UUID

from pydantic import BaseModel, Field


class EventIn(BaseModel):
    project_id: int
    event_type_id: int
    json_version_internal: str = Field(default="1.0", max_length=30)
    payload: dict
    event_uuid: UUID | None = None


class EventReceived(BaseModel):
    id: int
    event_uuid: UUID
    project_id: int
    event_type_id: int
    json_version_internal: str
    payload: dict
    status: str

    model_config = {
        "from_attributes": True
    }