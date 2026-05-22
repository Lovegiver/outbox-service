from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.event_repository import EventRepository
from app.services.event_service import EventService
from app.services.schema_validation_service import SchemaValidationService

def get_event_service(
        db: Session = Depends(get_db)
) -> EventService:
    repository = EventRepository(db)
    schema_validator = SchemaValidationService()
    return EventService(repository, schema_validator)