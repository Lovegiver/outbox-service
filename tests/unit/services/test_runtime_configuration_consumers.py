from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.delivery_service import DeliveryService
from app.services.metric_runtime_service import MetricPlanExecutionResult
from app.worker import (
    metric_retry_delay_seconds,
    process_metric_plan_executions,
    retry_delay_seconds,
)


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

    def get_metric_retry_initial_delay_seconds(self) -> int:
        return 2

    def get_metric_retry_max_delay_seconds(self) -> int:
        return 30


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


def test_metric_retry_delay_uses_independent_runtime_configuration(monkeypatch):
    monkeypatch.setattr("app.worker.config_service", RetryConfigStub())

    assert metric_retry_delay_seconds(attempt_count=1) == 2
    assert metric_retry_delay_seconds(attempt_count=2) == 4
    assert metric_retry_delay_seconds(attempt_count=8) == 30


def test_metric_worker_batch_stops_without_invoking_delivery(monkeypatch) -> None:
    results = [
        MetricPlanExecutionResult(1, "SUCCEEDED", 1),
        None,
    ]

    class MetricExecutionServiceStub:
        def execute_next(self):
            return results.pop(0)

    monkeypatch.setattr(
        "app.worker.config_service.get_metric_execution_batch_size",
        lambda: 10,
    )
    monkeypatch.setattr(
        "app.worker.ServiceFactory.create_metric_plan_execution_service",
        lambda _db, retry_delay: MetricExecutionServiceStub(),
    )
    monkeypatch.setattr(
        "app.worker.deliver_one_delivery",
        lambda *_args, **_kwargs: pytest.fail("metric retry replayed a delivery"),
    )
    monkeypatch.setattr(
        "app.worker.deliver_pending_deliveries",
        lambda *_args, **_kwargs: pytest.fail("metric retry replayed deliveries"),
    )

    processed = process_metric_plan_executions(SimpleNamespace())

    assert processed == (MetricPlanExecutionResult(1, "SUCCEEDED", 1),)
