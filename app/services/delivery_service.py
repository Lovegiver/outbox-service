import httpx

from app.core.delivery_status import DeliveryStatus
from app.models import Event, EventDelivery


class DeliveryService:

    def _build_headers(
            self,
            delivery: EventDelivery,
    ) -> dict[str, str]:

        headers = {}

        # TODO:
        # récupérer auth_type/auth_config/secret_ref
        # depuis RouteDefinition

        return headers

    def deliver(
            self,
            event: Event,
            delivery: EventDelivery,
    ) -> EventDelivery:

        if delivery.destination_type != "webhook":
            raise ValueError(
                f"Unsupported destination type: "
                f"{delivery.destination_type}"
            )

        if not delivery.destination_url:
            raise ValueError(
                f"No destination URL "
                f"for delivery {delivery.id}"
            )

        headers = self._build_headers(
            delivery
        )

        response = httpx.post(
            delivery.destination_url,
            json=event.payload,
            headers=headers,
            timeout=5.0,
        )

        response.raise_for_status()

        delivery.status = (
            DeliveryStatus.DELIVERED
        )

        delivery.attempt_count += 1
        delivery.last_error = None

        return delivery