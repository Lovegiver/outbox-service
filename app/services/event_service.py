from uuid import UUID
from jsonschema import ValidationError

from fastapi import HTTPException
from app.core.event_status import EventStatus

from app.core.event_status import EventStatus
from app.models import Event
from app.repositories.event_repository import EventRepository
from app.services.schema_validation_service import SchemaValidationService

class EventService:
    def __init__(
            self,
            repository: EventRepository,
            schema_validator: SchemaValidationService
    ):
        self.repository = repository
        self.schema_validator = schema_validator

    def receive_event(self, event_in) -> Event:
        event = Event(
            event_id=event_in.event_id,
            project=event_in.project,
            event_type=event_in.event_type,
            schema_version=event_in.schema_version,
            payload=event_in.payload,
            status=EventStatus.RECEIVED,
        )

        return self.repository.save(event)

    def rollback(self) -> None:
        self.repository.rollback()

    def validate_event(self, event_id: UUID) -> Event:
        event = self.repository.find_by_event_id(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail="Event not found"
            )

        if event.status != EventStatus.RECEIVED:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot validate event with status {event.status}"
            )

        try:
            self.schema_validator.validate_payload(
                project=event.project,
                event_type=event.event_type,
                payload=event.payload,
            )
        except FileNotFoundError as exc:
            event.status = EventStatus.FAILED
            self.repository.commit()
            raise HTTPException(
                status_code=422,
                detail=str(exc)
            ) from exc
        except ValidationError as exc:
            event.status = EventStatus.FAILED
            self.repository.commit()
            raise HTTPException(
                status_code=422,
                detail=f"Payload does not match schema: {exc.message}"
            ) from exc

        event.status = EventStatus.VALIDATED
        self.repository.commit()
        return event