from datetime import datetime, UTC
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.delivery_status import DeliveryStatus
from app.core.event_status import EventStatus
from app.database import get_db
from app.repositories.event_delivery_repository import EventDeliveryRepository
from app.repositories.event_repository import EventRepository
from app.schemas.runtime_metrics_schema import RuntimeMetricsSummary


router = APIRouter(
    prefix="/api/runtime/metrics",
    tags=["runtime-metrics"],
)


@router.get(
    "/summary",
    response_model=RuntimeMetricsSummary,
)
def get_runtime_metrics_summary(
    db: Session = Depends(get_db),
) -> RuntimeMetricsSummary:
    """
    Return the durable runtime metrics summary for the OB1 dashboard.

    The summary is computed from PostgreSQL, which is the operational source of
    truth. Runtime WebSocket events are useful for live animation and timeline
    updates, but dashboard counters should be hydrated from this endpoint.
    """

    event_repository = EventRepository(db)
    delivery_repository = EventDeliveryRepository(db)

    pending_events = event_repository.count_by_status(
        EventStatus.RECEIVED
    )
    deliveries_pending = delivery_repository.count_by_status(
        DeliveryStatus.PENDING
    )

    return RuntimeMetricsSummary(
        generated_at=datetime.now(UTC),

        events_routed=event_repository.count_by_status(EventStatus.ROUTED),
        events_unroutable=event_repository.count_by_status(
            EventStatus.UNROUTABLE
        ),
        events_failed=event_repository.count_by_status(EventStatus.FAILED),
        events_total=event_repository.count_all(),

        deliveries_created=delivery_repository.count_all(),
        deliveries_pending=deliveries_pending,
        deliveries_succeeded=delivery_repository.count_by_status(
            DeliveryStatus.DELIVERED
        ),
        deliveries_failed=delivery_repository.count_by_status(
            DeliveryStatus.FAILED
        ),
        dead_letters=delivery_repository.count_by_status(
            DeliveryStatus.DEAD_LETTER
        ),

        retry_count=delivery_repository.count_retries(),

        pending_events=pending_events,
        pending_deliveries=deliveries_pending,

        oldest_received_age_seconds=(
            event_repository.get_oldest_received_age_seconds()
        ),
        oldest_pending_delivery_age_seconds=(
            delivery_repository.get_oldest_pending_age_seconds()
        ),
    )