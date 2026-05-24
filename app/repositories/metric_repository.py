from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.system_metric import SystemMetric


class MetricRepository:

    def __init__(self, db: Session):
        self.db = db

    def count_received_events(
        self,
        period_start: datetime,
        period_end: datetime,
    ):
        statement = (
            select(
                Event.project_id.label("project_id"),
                Event.event_type_id.label("event_type_id"),
                func.count(Event.id).label("value"),
            )
            .where(
                Event.created_at >= period_start,
                Event.created_at < period_end,
            )
            .group_by(
                Event.project_id,
                Event.event_type_id,
            )
        )

        return self.db.execute(statement).all()

    def save_metric(
        self,
        metric_code: str,
        project_id: int | None,
        event_type_id: int | None,
        period_start: datetime,
        period_end: datetime,
        value: int,
    ) -> SystemMetric:
        metric = SystemMetric(
            metric_code=metric_code,
            project_id=project_id,
            event_type_id=event_type_id,
            period_start=period_start,
            period_end=period_end,
            value=value,
        )

        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)

        return metric