from sqlalchemy.orm import Session

from app.repositories.event_repository import EventRepository
from app.services.config_service import ConfigService
from app.services.delivery_service import DeliveryService
from app.services.event_service import EventService
from app.services.routing_service import RoutingService
from app.services.schema_validation_service import SchemaValidationService


class ServiceFactory:
    config_service = ConfigService()
    schema_validator = SchemaValidationService()
    routing_service = RoutingService()
    delivery_service = DeliveryService()

    @classmethod
    def create_event_service(
            cls,
            db: Session,
    ) -> EventService:
        repository = EventRepository(db)

        return EventService(
            repository=repository,
            schema_validator=cls.schema_validator,
            routing_service=cls.routing_service,
            delivery_service=cls.delivery_service,
            config_service=cls.config_service,
        )