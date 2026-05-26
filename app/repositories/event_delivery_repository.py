from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.delivery_status import DeliveryStatus
from app.models import EventDelivery


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