from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event


class EventRepository:

    def __init__(self, db: Session):
        self.db = db

    def save(self, event: Event) -> Event:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_by_id(self, event_id: int) -> Event | None:
        statement = select(Event).where(Event.id == event_id)
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_uuid(self, event_uuid: UUID) -> Event | None:
        statement = select(Event).where(Event.event_uuid == event_uuid)
        return self.db.execute(statement).scalar_one_or_none()