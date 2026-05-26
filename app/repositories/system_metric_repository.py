from datetime import datetime, timedelta, UTC

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.delivery_status import DeliveryStatus
from app.models import Project, EventType
from app.models.event_delivery import EventDelivery
from app.models.system_metric import SystemMetric


class SystemMetricRepository:

    def __init__(
            self,
            db: Session,
    ):
        self.db = db

    def _get_outbox_context(self) -> tuple[int, int]:
        statement = (
            select(Project.id, EventType.id)
            .join(EventType, EventType.project_id == Project.id)
            .where(
                Project.name == "OUTBOX",
                EventType.code == "OUTBOX_EVENT",
            )
        )

        result = self.db.execute(statement).one_or_none()

        if result is None:
            raise ValueError(
                "OUTBOX / OUTBOX_EVENT context not found"
            )

        project_id, event_type_id = result

        return project_id, event_type_id

    def _update_metric(
            self,
            metric_code: str,
            status: DeliveryStatus,
    ) -> None:
        count = (
            self.db.execute(
                select(
                    func.count()
                )
                .select_from(
                    EventDelivery
                )
                .where(
                    EventDelivery.status == status
                )
            )
            .scalar_one()
        )

        self._upsert_metric(
            metric_code=metric_code,
            value=count,
        )

    def _upsert_metric(
            self,
            metric_code: str,
            value: int,
    ) -> None:
        project_id, event_type_id = (
            self._get_outbox_context()
        )

        now = datetime.now(UTC)

        period_start = now.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        period_end = (
                period_start
                + timedelta(hours=1)
        )

        statement = (
            insert(SystemMetric)
            .values(
                metric_code=metric_code,
                project_id=project_id,
                event_type_id=event_type_id,
                period_start=period_start,
                period_end=period_end,
                value=value,
            )
            .on_conflict_do_update(
                constraint="uq_system_metric_period",
                set_={
                    "value": value,
                    "computed_at": now,
                }
            )
        )

        self.db.execute(statement)

    def update_dead_letter_metric(
            self,
    ) -> None:

        now = datetime.now(UTC)

        period_start = now.replace(
            minute=0,
            second=0,
            microsecond=0,
        )

        period_end = (
                period_start
                + timedelta(hours=1)
        )

        dead_letter_count = (
            self.db.execute(
                select(
                    func.count()
                )
                .select_from(
                    EventDelivery
                )
                .where(
                    EventDelivery.status
                    == DeliveryStatus.DEAD_LETTER
                )
            )
            .scalar()
        )

        project_id, event_type_id = self._get_outbox_context()

        statement = (
            insert(SystemMetric)
            .values(
                metric_code="delivery.dead_letter.total",
                project_id=project_id,
                event_type_id=event_type_id,
                period_start=period_start,
                period_end=period_end,
                value=dead_letter_count,
            )
            .on_conflict_do_update(
                constraint="uq_system_metric_period",
                set_={
                    "value": dead_letter_count,
                    "computed_at": now,
                }
            )
        )

        self.db.execute(statement)

    def update_delivered_metric(self) -> None:
        self._update_metric(
            metric_code="delivery.delivered.total",
            status=DeliveryStatus.DELIVERED,
        )

    def update_retry_metric(self) -> None:
        retry_count = (
            self.db.execute(
                select(
                    func.coalesce(
                        func.sum(
                            EventDelivery.attempt_count - 1
                        ),
                        0,
                    )
                )
                .where(
                    EventDelivery.attempt_count > 1
                )
            )
            .scalar_one()
        )

        self._upsert_metric(
            metric_code="delivery.retry.total",
            value=retry_count,
        )

    