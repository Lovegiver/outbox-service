from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DeadLetterRead(BaseModel):
    delivery_id: int
    event_id: int
    event_uuid: UUID
    project_id: int
    event_type_id: int
    destination_name: str
    destination_type: str
    destination_url: str | None
    status: str
    attempt_count: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class DeadLetterRetryResponse(BaseModel):
    delivery_id: int
    status: str
    attempt_count: int


class DeadLetterRetryAllResponse(BaseModel):
    project_id: int
    retried_count: int