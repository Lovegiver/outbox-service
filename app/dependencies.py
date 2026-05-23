from app.container.service_factory import ServiceFactory
from app.database import get_db
from app.services.event_service import EventService
from fastapi import Depends
from sqlalchemy.orm import Session


def get_event_service(
        db: Session = Depends(get_db)
) -> EventService:
    return ServiceFactory.create_event_service(db)