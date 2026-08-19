from app.core.delivery_status import DeliveryStatus
from app.repositories.event_delivery_repository import EventDeliveryRepository
from app.schemas.dead_letter_schema import (
    DeadLetterRead,
    DeadLetterRetryAllResponse,
    DeadLetterRetryResponse,
)
from sqlalchemy.orm import Session


class DeadLetterService:

    def __init__(
            self,
            db: Session,
            repository: EventDeliveryRepository,
    ):
        self.db = db
        self.repository = repository

    def list_dead_letters_by_project(
            self,
            project_id: int,
    ) -> list[DeadLetterRead]:

        deliveries = self.repository.find_dead_letters_by_project(
            project_id=project_id,
        )

        return [
            DeadLetterRead(
                delivery_id=delivery.id,
                event_id=delivery.event_id,
                event_uuid=delivery.event.event_uuid,
                project_id=delivery.event.project_id,
                event_type_id=delivery.event.event_type_id,
                destination_name=delivery.destination_name,
                destination_type=delivery.destination_type,
                destination_url=delivery.destination_url,
                status=delivery.status,
                attempt_count=delivery.attempt_count,
                last_error=delivery.last_error,
                created_at=delivery.created_at,
                updated_at=delivery.updated_at,
            )
            for delivery in deliveries
        ]

    def retry_dead_letter(
            self,
            project_id: int,
            delivery_id: int,
    ) -> DeadLetterRetryResponse:

        delivery = self.repository.find_by_id(delivery_id)

        if delivery is None:
            raise ValueError(f"Dead letter not found: {delivery_id}")

        if delivery.event.project_id != project_id:
            raise ValueError(f"Dead letter not found: {delivery_id}")

        if delivery.status != DeliveryStatus.DEAD_LETTER:
            raise ValueError(
                f"Delivery is not DEAD_LETTER: {delivery_id}"
            )

        self._reset_for_retry(delivery)

        self.repository.save(delivery)
        self.db.commit()
        self.db.refresh(delivery)

        return DeadLetterRetryResponse(
            delivery_id=delivery.id,
            status=delivery.status,
            attempt_count=delivery.attempt_count,
        )

    def retry_all_dead_letters_by_project(
            self,
            project_id: int,
    ) -> DeadLetterRetryAllResponse:

        deliveries = self.repository.find_dead_letters_by_project(
            project_id=project_id,
        )

        for delivery in deliveries:
            self._reset_for_retry(delivery)
            self.repository.save(delivery)

        self.db.commit()

        return DeadLetterRetryAllResponse(
            project_id=project_id,
            retried_count=len(deliveries),
        )

    @staticmethod
    def _reset_for_retry(delivery) -> None:
        delivery.status = DeliveryStatus.PENDING
        delivery.last_error = None
        delivery.attempt_count = 0
        delivery.next_attempt_at = None
