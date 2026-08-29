from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.processing_chain import ProcessingChain


class ProcessingChainRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, chain: ProcessingChain) -> ProcessingChain:
        self.db.add(chain)
        self.db.flush()
        return chain

    def find_active(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> ProcessingChain | None:
        statement = select(ProcessingChain).where(
            ProcessingChain.event_type_id == event_type_id,
            ProcessingChain.schema_definition_id == schema_definition_id,
            ProcessingChain.is_active.is_(True),
            ProcessingChain.status == "ACTIVE",
        )

        return self.db.execute(statement).scalar_one_or_none()

    def find_by_id(self, processing_chain_id: int) -> ProcessingChain | None:
        """Return one chain without changing transaction ownership."""
        statement = select(ProcessingChain).where(
            ProcessingChain.id == processing_chain_id
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list_by_scope(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> list[ProcessingChain]:
        """Return immutable snapshots from newest to oldest."""
        statement = (
            select(ProcessingChain)
            .where(
                ProcessingChain.event_type_id == event_type_id,
                ProcessingChain.schema_definition_id == schema_definition_id,
            )
            .order_by(
                ProcessingChain.version_number.desc(),
                ProcessingChain.id.desc(),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def list_active_by_event_type(self, event_type_id: int) -> list[ProcessingChain]:
        """Return active snapshots for every exact schema of one EventType."""
        statement = (
            select(ProcessingChain)
            .where(
                ProcessingChain.event_type_id == event_type_id,
                ProcessingChain.is_active.is_(True),
                ProcessingChain.status == "ACTIVE",
            )
            .order_by(ProcessingChain.schema_definition_id.asc(), ProcessingChain.id.asc())
        )
        return list(self.db.execute(statement).scalars().all())

    def find_next_version_number(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> int:
        statement = (
            select(ProcessingChain.version_number)
            .where(
                ProcessingChain.event_type_id == event_type_id,
                ProcessingChain.schema_definition_id == schema_definition_id,
            )
            .order_by(ProcessingChain.version_number.desc())
            .limit(1)
        )

        current_max = self.db.execute(statement).scalar_one_or_none()

        if current_max is None:
            return 1

        return current_max + 1
