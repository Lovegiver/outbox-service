import httpx

from app.core.delivery_status import DeliveryStatus
from app.models import Event, EventDelivery


class DeliveryService:
    def deliver(
            self,
            event: Event,
            delivery: EventDelivery,
    ) -> EventDelivery:
        if delivery.destination_type != "webhook":
            raise ValueError(
                f"Unsupported destination type: {delivery.destination_type}"
            )

        if not delivery.destination_url:
            raise ValueError(
                f"No destination URL for delivery {delivery.id}"
            )

        payload = {
            "event_uuid": str(event.event_uuid),
            "project_id": event.project_id,
            "event_type_id": event.event_type_id,
            "schema_version": event.schema_version,
            "payload": event.payload,
        }

        response = httpx.post(
            delivery.destination_url,
            json=payload,
            timeout=5.0,
        )

        response.raise_for_status()

        delivery.status = DeliveryStatus.DELIVERED
        delivery.attempt_count += 1
        delivery.last_error = None

        return delivery