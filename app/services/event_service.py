from uuid import uuid4, UUID

from sqlalchemy.orm import Session

from app.core.event_status import EventStatus
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.schemas.event_schema import EventIn, EventReceived
from app.services.schema_validation_service import SchemaValidationService


class EventService:

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
        self.schema_validation_service.validate_payload(
            event_type_id=event_in.event_type_id,
            json_version_internal=event_in.json_version_internal,
            payload=event_in.payload,
        )

        event = Event(
            event_uuid=event_in.event_uuid or uuid4(),
            project_id=event_in.project_id,
            event_type_id=event_in.event_type_id,
            json_version_internal=event_in.json_version_internal,
            payload=event_in.payload,
            status=EventStatus.RECEIVED.value,
        )

        saved_event = self.event_repository.save(event)

        return EventReceived.model_validate(saved_event)

    def get_event_by_id(self, event_id: int) -> EventReceived | None:
        event = self.event_repository.get_by_id(event_id)

        if event is None:
            return None

        return EventReceived.model_validate(event)

    def get_event_by_uuid(
            self,
            event_uuid: UUID
    ) -> EventReceived | None:

        event = self.event_repository.get_by_uuid(event_uuid)

        if event is None:
            return None

        return EventReceived.model_validate(event)

    def mark_event_as_validated(self, event_id: int) -> EventReceived | None:
        event = self.event_repository.get_by_id(event_id)

        if event is None:
            return None

        event.status = EventStatus.VALIDATED.value
        saved_event = self.event_repository.save(event)

        return EventReceived.model_validate(saved_event)

    def mark_event_as_routed(self, event_id: int) -> EventReceived | None:
        event = self.event_repository.get_by_id(event_id)

        if event is None:
            return None

        event.status = EventStatus.ROUTED.value
        saved_event = self.event_repository.save(event)

        return EventReceived.model_validate(saved_event)

    def mark_event_as_delivered(self, event_id: int) -> EventReceived | None:
        event = self.event_repository.get_by_id(event_id)

        if event is None:
            return None

        event.status = EventStatus.DELIVERED.value
        saved_event = self.event_repository.save(event)

        return EventReceived.model_validate(saved_event)

    def mark_event_as_failed(self, event_id: int) -> EventReceived | None:
        event = self.event_repository.get_by_id(event_id)

        if event is None:
            return None

        event.status = EventStatus.FAILED.value
        saved_event = self.event_repository.save(event)

        return EventReceived.model_validate(saved_event)

    def mark_event_as_dead_letter(self, event_id: int) -> EventReceived | None:
        event = self.event_repository.get_by_id(event_id)

        if event is None:
            return None

        event.status = EventStatus.DEAD_LETTER.value
        saved_event = self.event_repository.save(event)

        return EventReceived.model_validate(saved_event)