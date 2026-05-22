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