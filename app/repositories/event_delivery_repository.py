from app.core.delivery_status import DeliveryStatus
from app.models import EventDelivery
from app.models.event import Event
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session


class EventDeliveryRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, delivery: EventDelivery) -> EventDelivery:
        self.db.add(delivery)
        self.db.flush()
        self.db.refresh(delivery)
        return delivery

    def save(self, delivery: EventDelivery) -> EventDelivery:
        self.db.flush()
        self.db.refresh(delivery)
        return delivery

    def find_pending(self, limit: int = 50) -> list[EventDelivery]:
        statement = (
            select(EventDelivery)
            .where(EventDelivery.status == DeliveryStatus.PENDING)
            .order_by(EventDelivery.created_at.asc())
            .limit(limit)
        )

        return list(self.db.execute(statement).scalars().all())

    def find_by_id(self, delivery_id: int) -> EventDelivery | None:
        statement = (
            select(EventDelivery)
            .where(EventDelivery.id == delivery_id)
        )

        return self.db.execute(statement).scalar_one_or_none()

    def find_pending_and_retryable(
            self,
            max_attempts: int,
    ) -> list[EventDelivery]:
        statement = (
            select(EventDelivery)
            .where(
                or_(
                    EventDelivery.status == DeliveryStatus.PENDING,

                    and_(
                        EventDelivery.status == DeliveryStatus.FAILED,
                        EventDelivery.attempt_count < max_attempts,
                    ),
                )
            )
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def find_dead_letters(
            self,
            limit: int = 100,
    ) -> list[EventDelivery]:
        statement = (
            select(EventDelivery)
            .where(
                EventDelivery.status
                == DeliveryStatus.DEAD_LETTER
            )
            .order_by(
                EventDelivery.updated_at.desc()
            )
            .limit(limit)
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def find_dead_letters_by_project(
            self,
            project_id: int,
            limit: int = 100,
    ) -> list[EventDelivery]:
        statement = (
            select(EventDelivery)
            .join(Event)
            .where(Event.project_id == project_id)
            .where(EventDelivery.status == DeliveryStatus.DEAD_LETTER)
            .order_by(EventDelivery.updated_at.desc())
            .limit(limit)
        )

        return list(self.db.execute(statement).scalars().all())

