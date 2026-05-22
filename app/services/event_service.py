from app.models import Event
from app.repositories.event_repository import EventRepository


class EventService:
    def __init__(self, repository: EventRepository):
        self.repository = repository

    def receive_event(self, event_in) -> Event:
        event = Event(
            event_id=event_in.event_id,
            project=event_in.project,
            event_type=event_in.event_type,
            schema_version=event_in.schema_version,
            payload=event_in.payload,
            status="RECEIVED",
        )

        return self.repository.save(event)

    def rollback(self) -> None:
        self.repository.rollback()