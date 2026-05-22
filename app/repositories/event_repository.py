from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, event: Event) -> Event:
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def rollback(self) -> None:
        self.db.rollback()

    def find_by_event_id(self, event_id: UUID) -> Event | None:
        statement = select(Event).where(
            Event.event_id == event_id
        )

        return self.db.execute(statement).scalar_one_or_none()

    def commit(self) -> None:
        self.db.commit()