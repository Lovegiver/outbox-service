from datetime import datetime, UTC
from sqlalchemy import func
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import Session
from typing import Optional

from app.core.delivery_status import DeliveryStatus
from app.models import EventDelivery
from app.models.event import Event



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
            limit: int = 100,
    ) -> list[EventDelivery]:
        """
        Find deliveries eligible for execution or retry.

        The query uses PostgreSQL row-level locking with SKIP LOCKED so that
        multiple worker processes can safely claim distinct deliveries without
        executing the same delivery concurrently.

        Args:
            max_attempts: Maximum delivery attempts before dead-lettering.
            limit: Maximum number of deliveries to fetch in this batch.

        Returns:
            Deliveries locked by the current transaction and ready to process.
        """

        statement = (
            select(EventDelivery)
            .where(
                or_(
                    EventDelivery.status == DeliveryStatus.PENDING,
                    and_(
                        EventDelivery.status == DeliveryStatus.FAILED,
                        EventDelivery.attempt_count < max_attempts,
                        or_(
                            EventDelivery.next_attempt_at.is_(None),
                            EventDelivery.next_attempt_at <= func.now(),
                        ),
                    ),
                )
            )
            .order_by(EventDelivery.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
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

    def count_all(self) -> int:
        """
        Count all delivery records.

        Returns:
            Total number of delivery records stored in the database.
        """

        statement = select(func.count()).select_from(EventDelivery)

        return int(self.db.execute(statement).scalar_one())

    def count_by_status(self, status: DeliveryStatus) -> int:
        """
        Count deliveries matching the given status.

        Args:
            status: Delivery lifecycle status to count.

        Returns:
            Number of deliveries currently stored with this status.
        """

        statement = (
            select(func.count())
            .select_from(EventDelivery)
            .where(EventDelivery.status == status)
        )

        return int(self.db.execute(statement).scalar_one())

    def count_retries(self) -> int:
        """
        Count retry attempts across all deliveries.

        Returns:
            Number of retry attempts, excluding the first attempt.
        """

        statement = (
            select(
                func.coalesce(
                    func.sum(EventDelivery.attempt_count - 1),
                    0,
                )
            )
            .where(EventDelivery.attempt_count > 1)
        )

        return int(self.db.execute(statement).scalar_one())

    def get_oldest_pending_age_seconds(self) -> Optional[int]:
        """
        Compute the age in seconds of the oldest pending delivery.

        Returns:
            Age in seconds of the oldest PENDING delivery, or None when no
            delivery is waiting.
        """

        statement = (
            select(func.min(EventDelivery.created_at))
            .where(EventDelivery.status == DeliveryStatus.PENDING)
        )

        oldest_created_at = self.db.execute(statement).scalar_one()

        if oldest_created_at is None:
            return None

        return int(
            (datetime.now(UTC) - oldest_created_at).total_seconds()
        )
