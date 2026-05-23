from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.event_repository import EventRepository
from app.services.delivery_service import DeliveryService
from app.services.event_service import EventService
from app.services.routing_service import RoutingService
from app.services.schema_validation_service import SchemaValidationService

def get_event_service(
        db: Session = Depends(get_db)
) -> EventService:
    repository = EventRepository(db)
    schema_validator = SchemaValidationService()
    routing_service = RoutingService()
    delivery_service = DeliveryService()

    return EventService(
        repository,
        schema_validator,
        routing_service,
        delivery_service
    )