from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.delivery_service import DeliveryService
from app.worker import retry_delay_seconds


class DeliveryConfigStub:
    def __init__(self, *, timeout: int = 7, require_https: bool = False):
        self.timeout = timeout
        self.require_https = require_https

    def get_delivery_timeout_seconds(self) -> int:
        return self.timeout

    def is_delivery_https_required(self) -> bool:
        return self.require_https

    def get_destination_secret_provider(self) -> str:
        return "environment"


class RetryConfigStub:
    def get_retry_strategy(self) -> str:
        return "exponential"

    def get_retry_delay_seconds(self) -> int:
        return 5

    def get_retry_max_delay_seconds(self) -> int:
        return 600

    def is_retry_jitter_enabled(self) -> bool:
        return False


def test_delivery_uses_runtime_timeout_and_event_idempotency_headers(monkeypatch):
    captured = {}

    class ResponseStub:
        def raise_for_status(self) -> None:
            return None

    def post_stub(url, json, headers, timeout):
        captured.update(
            url=url,
            json=json,
            headers=headers,
            timeout=timeout,
        )
        return ResponseStub()

    monkeypatch.setattr("app.services.delivery_service.httpx.post", post_stub)

    event_uuid = uuid4()
    event = SimpleNamespace(
        event_uuid=event_uuid,
        correlation_id="7dc6b60f-0051-4771-aeba-02c47788f441",
        payload={"duration_seconds": 12.3},
    )
    delivery = SimpleNamespace(
        id=42,
        destination_type="webhook",
        destination_url="http://consumer.test/events",
        status="PENDING",
        attempt_count=0,
        last_error=None,
    )

    DeliveryService(DeliveryConfigStub(timeout=7)).deliver(event, delivery)

    assert captured["timeout"] == 7
    assert captured["json"] == event.payload
    assert captured["headers"]["Idempotency-Key"] == str(event_uuid)
    assert captured["headers"]["X-Outbox-Event-Id"] == str(event_uuid)


def test_delivery_enforces_https_when_runtime_requires_it():
    service = DeliveryService(DeliveryConfigStub(require_https=True))
    event = SimpleNamespace(event_uuid=uuid4(), correlation_id=None, payload={})
    delivery = SimpleNamespace(
        id=42,
        destination_type="webhook",
        destination_url="http://consumer.test/events",
    )

    with pytest.raises(ValueError, match="HTTPS is required"):
        service.deliver(event, delivery)


def test_delivery_resolves_api_key_from_configured_environment_provider(
    monkeypatch,
):
    captured = {}

    class ResponseStub:
        def raise_for_status(self) -> None:
            return None

    def post_stub(url, json, headers, timeout):
        captured["headers"] = headers
        return ResponseStub()

    monkeypatch.setenv("BLACKHOLE_API_KEY", "destination-secret")
    monkeypatch.setattr("app.services.delivery_service.httpx.post", post_stub)

    event = SimpleNamespace(event_uuid=uuid4(), correlation_id=None, payload={})
    delivery = SimpleNamespace(
        id=42,
        destination_type="webhook",
        destination_url="https://consumer.test/events",
        auth_type="API_KEY_HEADER",
        auth_config={"header_name": "X-API-Key"},
        secret_ref="BLACKHOLE_API_KEY",
        status="PENDING",
        attempt_count=0,
        last_error=None,
    )

    DeliveryService(DeliveryConfigStub()).deliver(event, delivery)

    assert captured["headers"]["X-API-Key"] == "destination-secret"


def test_retry_delay_uses_exponential_runtime_configuration(monkeypatch):
    monkeypatch.setattr("app.worker.config_service", RetryConfigStub())

    assert retry_delay_seconds(attempt_count=1) == 5
    assert retry_delay_seconds(attempt_count=2) == 10
    assert retry_delay_seconds(attempt_count=8) == 600
