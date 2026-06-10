from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.runtime.runtime_event_type import RuntimeEventType


class RuntimeEvent(BaseModel):
    """
    Runtime event emitted by the real OB1 backend pipeline.

    This object is intentionally observational. It describes what happened
    inside the pipeline but does not drive business execution.
    """

    type: RuntimeEventType
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    event_id: Optional[int] = None
    event_uuid: Optional[UUID] = None
    event_type_id: Optional[int] = None
    correlation_id: Optional[str] = None
    event_status: Optional[str] = None

    delivery_id: Optional[int] = None
    delivery_status: Optional[str] = None
    
    message: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)