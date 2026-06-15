from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RuntimeMetricsSummary(BaseModel):
    """
    Database-backed runtime metrics summary exposed to the admin dashboard.

    The response represents the durable operational state stored in PostgreSQL.
    WebSocket runtime events may animate the UI, but this summary remains the
    source of truth for dashboard counters and ratios.
    """

    generated_at: datetime

    events_routed: int
    events_unroutable: int
    events_failed: int
    events_total: int

    deliveries_created: int
    deliveries_pending: int
    deliveries_succeeded: int
    deliveries_failed: int
    dead_letters: int

    retry_count: int

    pending_events: int
    pending_deliveries: int

    oldest_received_age_seconds: Optional[int]
    oldest_pending_delivery_age_seconds: Optional[int]