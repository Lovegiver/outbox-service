from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.event_status import EventStatus
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.schemas.event_schema import EventIn, EventReceived
from app.services.schema_validation_service import SchemaValidationService


class EventIngressService:
    """
    Service responsible for ingesting incoming Outbox events.

    This service is the transactional boundary of the ingress layer.
    It validates the incoming event against the active client JSON schema,
    persists the event with the RECEIVED status, commits the ingestion
    transaction, and returns the persisted event representation.

    It intentionally does not execute the secondary processing pipeline.
    Metrics extraction, routing, delivery creation, retries, and dead-letter
    management are handled asynchronously by the worker layer.
    """

    def __init__(
        self,
        db: Session,
        event_repository: EventRepository,
        schema_validation_service: SchemaValidationService,
    ):
        self.db = db
        self.event_repository = event_repository
        self.schema_validation_service = schema_validation_service

    def receive_event(self, event_in: EventIn) -> EventReceived:
        """
        Validate and persist an incoming Outbox event.

        Args:
            event_in: Incoming event payload containing project, event type,
                JSON schema version, optional event UUID, and business payload.

        Returns:
            The persisted event representation after the ingestion transaction
            has been committed.

        Raises:
            ValueError: If no matching active schema can validate the payload.
            jsonschema.ValidationError: If the payload does not match the active
            client schema.
        """

        schema_definition = self.schema_validation_service.validate_payload(
            event_type_id=event_in.event_type_id,
            json_version_internal=event_in.json_version_internal,
            payload=event_in.payload,
        )

        event = Event(
            event_uuid=event_in.event_uuid or uuid4(),
            project_id=event_in.project_id,
            event_type_id=event_in.event_type_id,
            schema_definition_id=schema_definition.id,
            json_version_internal=event_in.json_version_internal,
            payload=event_in.payload,
            status=EventStatus.RECEIVED.value,
            correlation_id=event_in.correlation_id,
        )

        saved_event = self.event_repository.save(event)

        self.db.commit()
        self.db.refresh(saved_event)

        return EventReceived.model_validate(saved_event)

    def get_event_by_id(self, event_id: int) -> EventReceived | None:
        event = self.event_repository.get_by_id(event_id)

        if event is None:
            return None

        return EventReceived.model_validate(event)

    def get_event_by_uuid(self, event_uuid: UUID) -> EventReceived | None:
        event = self.event_repository.get_by_uuid(event_uuid)

        if event is None:
            return None

        return EventReceived.model_validate(event)
