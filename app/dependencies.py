from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.event_repository import EventRepository
from app.services.event_service import EventService


def get_event_service(
        db: Session = Depends(get_db)
) -> EventService:
    repository = EventRepository(db)
    return EventService(repository)