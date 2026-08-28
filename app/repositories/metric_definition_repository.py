from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metric_definition import MetricDefinition


class MetricDefinitionRepository:
    """Persist and load metric definitions without owning transactions."""

    def __init__(self, db: Session) -> None:
        """Initialize the repository with its caller-owned session."""
        self.db = db

    def add(self, metric_definition: MetricDefinition) -> MetricDefinition:
        """Add a metric definition to the current transaction."""
        self.db.add(metric_definition)
        self.db.flush()
        return metric_definition

    def find_by_id(
        self,
        metric_definition_id: int,
        *,
        for_update: bool = False,
    ) -> MetricDefinition | None:
        """Return a metric definition, optionally locking it for versioning."""
        statement = select(MetricDefinition).where(
            MetricDefinition.id == metric_definition_id
        )

        if for_update:
            statement = statement.with_for_update()

        return self.db.execute(statement).scalar_one_or_none()

    def find_by_event_type_and_code(
        self,
        event_type_id: int,
        code: str,
    ) -> MetricDefinition | None:
        """Return the definition identified by its natural Builder scope."""
        statement = select(MetricDefinition).where(
            MetricDefinition.event_type_id == event_type_id,
            MetricDefinition.code == code,
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list_by_event_type(self, event_type_id: int) -> list[MetricDefinition]:
        """Return definitions belonging to an EventType in stable order."""
        statement = (
            select(MetricDefinition)
            .where(MetricDefinition.event_type_id == event_type_id)
            .order_by(MetricDefinition.id.asc())
        )

        return list(self.db.execute(statement).scalars().all())
