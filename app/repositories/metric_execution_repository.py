from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.metric_execution_status import MetricPlanExecutionStatus
from app.models.metric_plan_execution import MetricPlanExecution
from app.models.metric_processing_execution import MetricProcessingExecution


class MetricExecutionRepository:
    """Persist and lock targeted metric runtime execution records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_processing_by_event_id(
        self, event_id: int
    ) -> MetricProcessingExecution | None:
        statement = select(MetricProcessingExecution).where(
            MetricProcessingExecution.event_id == event_id
        )
        return self.db.execute(statement).scalar_one_or_none()

    def create_processing_if_absent(
        self,
        *,
        event_id: int,
        processing_chain_id: int,
        status: str,
        last_error: str | None = None,
    ) -> MetricProcessingExecution:
        statement = (
            insert(MetricProcessingExecution)
            .values(
                event_id=event_id,
                processing_chain_id=processing_chain_id,
                status=status,
                last_error=last_error,
            )
            .on_conflict_do_nothing(constraint="uq_metric_processing_execution_event")
        )
        self.db.execute(statement)
        locked = (
            select(MetricProcessingExecution)
            .where(MetricProcessingExecution.event_id == event_id)
            .with_for_update()
        )
        return self.db.execute(locked).scalar_one()

    def create_plan_executions_if_absent(
        self,
        *,
        metric_processing_execution_id: int,
        event_id: int,
        processing_chain_id: int,
        processing_plan_ids: list[int],
    ) -> None:
        if not processing_plan_ids:
            return
        statement = (
            insert(MetricPlanExecution)
            .values(
                [
                    {
                        "metric_processing_execution_id": (
                            metric_processing_execution_id
                        ),
                        "event_id": event_id,
                        "processing_chain_id": processing_chain_id,
                        "processing_plan_id": processing_plan_id,
                        "status": MetricPlanExecutionStatus.PENDING,
                        "attempt_count": 0,
                        "is_retryable": True,
                    }
                    for processing_plan_id in processing_plan_ids
                ]
            )
            .on_conflict_do_nothing(constraint="uq_metric_plan_execution_event_plan")
        )
        self.db.execute(statement)

    def create_failed_plan_execution_if_absent(
        self,
        *,
        metric_processing_execution_id: int,
        event_id: int,
        processing_chain_id: int,
        processing_plan_id: int,
        last_error: str,
    ) -> None:
        """Persist an identifiable active-plan configuration defect."""
        statement = (
            insert(MetricPlanExecution)
            .values(
                metric_processing_execution_id=metric_processing_execution_id,
                event_id=event_id,
                processing_chain_id=processing_chain_id,
                processing_plan_id=processing_plan_id,
                status=MetricPlanExecutionStatus.FAILED_PERMANENT,
                attempt_count=0,
                last_error=last_error[:2000],
                is_retryable=False,
            )
            .on_conflict_do_nothing(constraint="uq_metric_plan_execution_event_plan")
        )
        self.db.execute(statement)

    def lock_next_eligible(
        self,
        *,
        max_attempts: int,
    ) -> MetricPlanExecution | None:
        statement = (
            select(MetricPlanExecution)
            .join(
                MetricProcessingExecution,
                MetricProcessingExecution.id
                == MetricPlanExecution.metric_processing_execution_id,
            )
            .where(
                MetricPlanExecution.attempt_count < max_attempts,
                or_(
                    MetricPlanExecution.status == MetricPlanExecutionStatus.PENDING,
                    and_(
                        MetricPlanExecution.status
                        == MetricPlanExecutionStatus.RETRYABLE,
                        or_(
                            MetricPlanExecution.next_attempt_at.is_(None),
                            MetricPlanExecution.next_attempt_at <= func.now(),
                        ),
                    ),
                ),
            )
            .order_by(
                MetricPlanExecution.next_attempt_at.asc().nullsfirst(),
                MetricPlanExecution.created_at.asc(),
                MetricPlanExecution.id.asc(),
            )
            .limit(1)
            .with_for_update(
                of=(MetricPlanExecution, MetricProcessingExecution),
                skip_locked=True,
            )
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list_plan_executions(
        self, metric_processing_execution_id: int
    ) -> list[MetricPlanExecution]:
        statement = (
            select(MetricPlanExecution)
            .where(
                MetricPlanExecution.metric_processing_execution_id
                == metric_processing_execution_id
            )
            .order_by(MetricPlanExecution.id.asc())
        )
        return list(self.db.execute(statement).scalars().all())

    def touch_processing(
        self, processing: MetricProcessingExecution
    ) -> MetricProcessingExecution:
        processing.updated_at = datetime.now(UTC)
        self.db.add(processing)
        self.db.flush()
        return processing
