from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, EventDelivery


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

    def find_by_event_id(self, event_id: UUID) -> Event | None:
        statement = select(Event).where(
            Event.event_id == event_id
        )

        return self.db.execute(statement).scalar_one_or_none()

    def commit(self) -> None:
        self.db.commit()

    def add_delivery(
            self,
            delivery: EventDelivery
    ) -> EventDelivery:
        self.db.add(delivery)
        return delivery

    def find_deliveries_by_event_id_and_status(
            self,
            event_id: int,
            status: str,
    ) -> list[EventDelivery]:
        statement = select(EventDelivery).where(
            EventDelivery.event_id == event_id,
            EventDelivery.status == status,
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def find_events_by_status(
            self,
            status: str,
    ) -> list[Event]:
        statement = select(Event).where(
            Event.status == status,
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )