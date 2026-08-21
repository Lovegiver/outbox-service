from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.processing_plan import ProcessingPlan


class ProcessingPlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_all(self, plans: list[ProcessingPlan]) -> list[ProcessingPlan]:
        self.db.add_all(plans)
        self.db.flush()
        return plans

    def list_active_by_chain_id(
        self,
        processing_chain_id: int,
    ) -> list[ProcessingPlan]:
        statement = (
            select(ProcessingPlan)
            .where(
                ProcessingPlan.processing_chain_id == processing_chain_id,
                ProcessingPlan.is_active.is_(True),
            )
            .order_by(ProcessingPlan.position.asc(), ProcessingPlan.id.asc())
        )

        return list(self.db.execute(statement).scalars().all())

    def list_by_chain_id(
        self,
        processing_chain_id: int,
    ) -> list[ProcessingPlan]:
        """Return every persisted plan in deterministic snapshot order."""
        statement = (
            select(ProcessingPlan)
            .where(ProcessingPlan.processing_chain_id == processing_chain_id)
            .order_by(ProcessingPlan.position.asc(), ProcessingPlan.id.asc())
        )
        return list(self.db.execute(statement).scalars().all())
