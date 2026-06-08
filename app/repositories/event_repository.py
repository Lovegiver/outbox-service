from uuid import UUID

from app.core.event_status import EventStatus
from app.models.event import Event
from sqlalchemy import select
from sqlalchemy.orm import Session


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

    def find_received(self, limit: int = 50) -> list[Event]:
        statement = (
            select(Event)
            .where(Event.status == EventStatus.RECEIVED)
            .order_by(Event.created_at.asc())
            .limit(limit)
        )

        return list(self.db.execute(statement).scalars().all())