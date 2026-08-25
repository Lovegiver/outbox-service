from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.analytical_observation import AnalyticalObservation


class AnalyticalObservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self,
        observation: AnalyticalObservation,
    ) -> AnalyticalObservation:
        self.db.add(observation)
        self.db.flush()
        return observation

    def add_all(
        self,
        observations: list[AnalyticalObservation],
    ) -> list[AnalyticalObservation]:
        self.db.add_all(observations)
        self.db.flush()
        return observations

    def find_by_event_id(
        self,
        event_id: int,
    ) -> list[AnalyticalObservation]:
        statement = (
            select(AnalyticalObservation)
            .where(AnalyticalObservation.event_id == event_id)
            .order_by(AnalyticalObservation.id)
        )

        return list(self.db.scalars(statement).all())

    def add_runtime_observation_if_absent(
        self,
        observation: AnalyticalObservation,
    ) -> bool:
        """Insert one deterministic runtime observation idempotently."""
        statement = (
            insert(AnalyticalObservation)
            .values(
                project_id=observation.project_id,
                event_type_id=observation.event_type_id,
                event_id=observation.event_id,
                metric_definition_id=observation.metric_definition_id,
                metric_definition_version_id=(observation.metric_definition_version_id),
                processing_chain_id=observation.processing_chain_id,
                processing_plan_id=observation.processing_plan_id,
                metric_plan_execution_id=observation.metric_plan_execution_id,
                observation_key=observation.observation_key,
                metric_code=observation.metric_code,
                value=observation.value,
                dimensions_json=observation.dimensions_json,
            )
            .on_conflict_do_nothing(
                constraint="uq_analytical_observation_runtime_identity"
            )
            .returning(AnalyticalObservation.id)
        )
        return self.db.execute(statement).scalar_one_or_none() is not None
