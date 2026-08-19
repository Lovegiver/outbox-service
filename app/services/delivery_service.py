import httpx
import os
from urllib.parse import urlsplit

from app.core.auth_type import AuthType
from app.core.delivery_status import DeliveryStatus
from app.models import Event, EventDelivery
from app.services.config_service import ConfigService


class DeliveryService:

    def __init__(self, config_service: ConfigService):
        self.config_service = config_service

    def _build_headers(
            self,
            event: Event,
            delivery: EventDelivery,
    ) -> dict[str, str]:

        headers = {
            "Idempotency-Key": str(event.event_uuid),
            "X-Outbox-Event-Id": str(event.event_uuid),
        }

        if event.correlation_id:
            headers["X-Outbox-Correlation-Id"] = event.correlation_id

        auth_type = getattr(delivery, "auth_type", AuthType.NONE)

        if auth_type == AuthType.NONE:
            return headers

        secret = self._resolve_destination_secret(
            getattr(delivery, "secret_ref", None)
        )

        if auth_type in {AuthType.API_KEY_HEADER, AuthType.API_KEY}:
            auth_config = getattr(delivery, "auth_config", None) or {}
            header_name = auth_config.get("header_name", "X-API-Key")

            if not isinstance(header_name, str) or not header_name.strip():
                raise ValueError("API key header name is required")

            headers[header_name] = secret
            return headers

        if auth_type in {AuthType.BEARER_TOKEN, AuthType.BEARER}:
            headers["Authorization"] = f"Bearer {secret}"
            return headers

        raise ValueError(f"Unsupported destination auth type: {auth_type}")

    def _resolve_destination_secret(self, secret_ref: str | None) -> str:
        if not secret_ref:
            raise ValueError("Destination secret reference is required")

        provider = self.config_service.get_destination_secret_provider()

        if provider != "environment":
            raise ValueError(
                f"Unsupported destination secret provider: {provider}"
            )

        secret = os.getenv(secret_ref)

        if not secret:
            raise ValueError(f"Destination secret not found: {secret_ref}")

        return secret

    def _validate_destination_url(self, destination_url: str) -> None:
        parsed_url = urlsplit(destination_url)

        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise ValueError("Destination URL must be an absolute HTTP(S) URL")

        if parsed_url.username or parsed_url.password:
            raise ValueError("Destination URL must not contain credentials")

        if (
            self.config_service.is_delivery_https_required()
            and parsed_url.scheme != "https"
        ):
            raise ValueError("HTTPS is required for delivery destinations")

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

        self._validate_destination_url(delivery.destination_url)

        headers = self._build_headers(
            event,
            delivery
        )

        response = httpx.post(
            delivery.destination_url,
            json=event.payload,
            headers=headers,
            timeout=self.config_service.get_delivery_timeout_seconds(),
        )

        response.raise_for_status()

        delivery.status = (
            DeliveryStatus.DELIVERED
        )

        delivery.attempt_count += 1
        delivery.last_error = None

        return delivery
