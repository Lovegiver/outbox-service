from uuid import UUID
from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.event_status import EventStatus
from app.models.event import Event


class EventRepository:

    def __init__(self, db: Session):
        self.db = db

    def save(self, event: Event) -> Event:
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def get_by_id(self, event_id: int) -> Event | None:
        statement = select(Event).where(Event.id == event_id)
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_uuid(self, event_uuid: UUID) -> Event | None:
        statement = select(Event).where(Event.event_uuid == event_uuid)
        return self.db.execute(statement).scalar_one_or_none()

    def find_received(self, limit: int = 100) -> list[Event]:
        """
        Find RECEIVED events eligible for worker processing.

        The query uses PostgreSQL row-level locking with SKIP LOCKED so that
        multiple worker processes can safely claim distinct batches without
        processing the same event concurrently.

        Args:
            limit: Maximum number of events to fetch in this batch.

        Returns:
            Events locked by the current transaction and ready to process.
        """

        statement = (
            select(Event)
            .where(Event.status == EventStatus.RECEIVED)
            .order_by(Event.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

        return list(self.db.execute(statement).scalars().all())

    def count_by_status(self, status: EventStatus) -> int:
        """
        Count events matching the given status.

        Args:
            status: Event lifecycle status to count.

        Returns:
            Number of events currently stored with this status.
        """

        statement = (
            select(func.count())
            .select_from(Event)
            .where(Event.status == status)
        )

        return int(self.db.execute(statement).scalar_one())

    def get_oldest_received_age_seconds(self) -> Optional[int]:
        """
        Compute the age in seconds of the oldest RECEIVED event.

        Returns:
            Age in seconds of the oldest pending event, or None when no event
            is currently waiting in RECEIVED status.
        """

        statement = (
            select(func.min(Event.created_at))
            .where(Event.status == EventStatus.RECEIVED)
        )

        oldest_created_at = self.db.execute(statement).scalar_one()

        if oldest_created_at is None:
            return None

        return int(
            (datetime.now(UTC) - oldest_created_at).total_seconds()
        )

    def count_all(self) -> int:
        """
        Count all persisted events.

        Returns:
            Total number of events stored in the database.
        """

        statement = select(func.count()).select_from(Event)

        return int(self.db.execute(statement).scalar_one())