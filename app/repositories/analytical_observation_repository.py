from __future__ import annotations

from sqlalchemy import select
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