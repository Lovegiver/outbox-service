from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx
from sqlalchemy import text
from pytest_bdd import given, parsers, then, when
from sqlalchemy import text

from app.worker import deliver_one_delivery, deliver_pending_deliveries
from tests.domain.record import EventDeliveryRecord
from tests.domain.record import EventRecord
from tests.domain.record import SchemaDefinitionRecord
from tests.infrastructure.context import TestContext


pending_delivery_pattern = parsers.parse(
    'project "{project_name}" has a routed Event with pending delivery "{destination_name}" to "{destination_url}"'
)
delivered_delivery_pattern = parsers.parse(
    'project "{project_name}" has a routed Event with delivered delivery "{destination_name}" to "{destination_url}"'
)
dead_letter_delivery_pattern = parsers.parse(
    'project "{project_name}" has a routed Event with dead-letter delivery "{destination_name}" to "{destination_url}"'
)
failed_delivery_pattern = parsers.parse(
    'project "{project_name}" has a routed Event '
    'with failed delivery "{destination_name}" '
    'to "{destination_url}" '
    'after {attempt_count:d} attempt'
)
delivery_status_pattern = parsers.parse(
    'delivery "{destination_name}" should have status "{status}"'
)
delivery_attempt_count_pattern = parsers.parse(
    'delivery "{destination_name}" should have attempt count {attempt_count:d}'
)
delivery_last_error_pattern = parsers.parse(
    'delivery "{destination_name}" should have last error containing "{expected_error}"'
)


@dataclass
class StubResponse:
    status_code: int = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                message=f"HTTP {self.status_code} Service Unavailable",
                request=httpx.Request("POST", "https://blackhole.example.test/webhook"),
                response=httpx.Response(self.status_code),
            )


def _state(ctx: TestContext) -> dict[str, Any]:
    state = getattr(ctx, "delivery_worker_state", None)

    if state is None:
        state = {"deliveries": {}, "http_calls": 0}
        setattr(ctx, "delivery_worker_state", state)

    return state


def _delivery(ctx: TestContext, destination_name: str):
    delivery = _state(ctx)["deliveries"].get(destination_name)

    if delivery is None:
        raise AssertionError(f"No delivery registered for destination {destination_name}.")

    return delivery


def _create_delivery_graph(
    ctx: TestContext,
    project_name: str,
    destination_name: str,
    destination_url: str,
    status: str,
    attempt_count: int = 0,
    last_error: Optional[str] = None,
) -> None:
    project = ctx.seed.project_registered(project_name)

    event_type = ctx.seed.event_type_registered(
        project=project,
        code="article.analyzed",
        name="Article analyzed",
    )

    schema_definition = ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=event_type,
            json_schema={
                "type": "object",
                "properties": {
                    "duration_seconds": {"type": "number"},
                },
                "required": ["duration_seconds"],
            },
        )
    )

    event = ctx.factory.event(
        EventRecord(
            event_type=event_type,
            schema_definition=schema_definition,
            payload={"duration_seconds": 12.3},
            status="ROUTED",
        )
    )

    delivery = ctx.factory.event_delivery(
        EventDeliveryRecord(
            event=event,
            destination_name=destination_name,
            destination_type="webhook",
            destination_url=destination_url,
            status=status,
            attempt_count=attempt_count,
            last_error=last_error,
        )
    )

    _state(ctx)["event"] = event
    _state(ctx)["deliveries"][destination_name] = delivery


@given(pending_delivery_pattern)
def project_has_routed_event_with_pending_delivery(
    ctx: TestContext,
    project_name: str,
    destination_name: str,
    destination_url: str,
) -> None:
    _create_delivery_graph(ctx, project_name, destination_name, destination_url, "PENDING")


@given(delivered_delivery_pattern)
def project_has_routed_event_with_delivered_delivery(
    ctx: TestContext,
    project_name: str,
    destination_name: str,
    destination_url: str,
) -> None:
    _create_delivery_graph(ctx, project_name, destination_name, destination_url, "DELIVERED", attempt_count=1)


@given(dead_letter_delivery_pattern)
def project_has_routed_event_with_dead_letter_delivery(
    ctx: TestContext,
    project_name: str,
    destination_name: str,
    destination_url: str,
) -> None:
    _create_delivery_graph(
        ctx,
        project_name,
        destination_name,
        destination_url,
        "DEAD_LETTER",
        attempt_count=3,
        last_error="Previous final failure",
    )


@given(failed_delivery_pattern)
def project_has_routed_event_with_failed_delivery(
    ctx: TestContext,
    project_name: str,
    destination_name: str,
    destination_url: str,
    attempt_count: int,
) -> None:
    _create_delivery_graph(
        ctx,
        project_name,
        destination_name,
        destination_url,
        "FAILED",
        attempt_count=attempt_count,
        last_error="Previous failure",
    )


@given("webhook deliveries will succeed")
def webhook_deliveries_will_succeed(ctx: TestContext, monkeypatch) -> None:
    def post_stub(*args, **kwargs):
        _state(ctx)["http_calls"] += 1
        return StubResponse(status_code=200)

    monkeypatch.setattr(httpx, "post", post_stub)


@given(parsers.parse('webhook deliveries will fail with "{error_message}"'))
def webhook_deliveries_will_fail(ctx: TestContext, monkeypatch, error_message: str) -> None:
    def post_stub(*args, **kwargs):
        _state(ctx)["http_calls"] += 1
        raise RuntimeError(error_message)

    monkeypatch.setattr(httpx, "post", post_stub)


@when("pending deliveries are processed by the delivery worker")
def pending_deliveries_are_processed(ctx: TestContext) -> None:
    deliver_pending_deliveries(ctx.db_session)


@then(delivery_status_pattern)
def delivery_should_have_status(ctx: TestContext, destination_name: str, status: str) -> None:
    assert ctx.probe.event_delivery.status_by_id(_delivery(ctx, destination_name).id) == status


@then(delivery_attempt_count_pattern)
def delivery_should_have_attempt_count(ctx: TestContext, destination_name: str, attempt_count: int) -> None:
    assert ctx.probe.event_delivery.attempt_count_by_id(_delivery(ctx, destination_name).id) == attempt_count


@then(parsers.parse('delivery "{destination_name}" should have no last error'))
def delivery_should_have_no_last_error(ctx: TestContext, destination_name: str) -> None:
    assert ctx.probe.event_delivery.last_error_by_id(_delivery(ctx, destination_name).id) is None


@then(delivery_last_error_pattern)
def delivery_should_have_last_error(ctx: TestContext, destination_name: str, expected_error: str) -> None:
    assert expected_error in ctx.probe.event_delivery.last_error_by_id(_delivery(ctx, destination_name).id)


@then("webhook delivery should not have been called")
def webhook_delivery_should_not_have_been_called(ctx: TestContext) -> None:
    assert _state(ctx)["http_calls"] == 0

@given(parsers.parse("max delivery attempts is {max_attempts:d}"))
def max_delivery_attempts_is(monkeypatch, max_attempts: int) -> None:
    import app.worker as worker_module

    monkeypatch.setattr(
        worker_module.config_service,
        "get_max_delivery_attempts",
        lambda: max_attempts,
    )


@given(parsers.parse('delivery "{destination_name}" has destination type "{destination_type}"'))
def delivery_has_destination_type(
    ctx: TestContext,
    destination_name: str,
    destination_type: str,
) -> None:
    delivery = _delivery(ctx, destination_name)

    ctx.db_session.execute(
        text(
            """
            UPDATE outbox.event_delivery
            SET destination_type = :destination_type
            WHERE id = :delivery_id
            """
        ),
        {
            "delivery_id": delivery.id,
            "destination_type": destination_type,
        },
    )


@given(parsers.parse('delivery "{destination_name}" has no destination URL'))
def delivery_has_no_destination_url(ctx: TestContext, destination_name: str) -> None:
    delivery = _delivery(ctx, destination_name)

    ctx.db_session.execute(
        text(
            """
            UPDATE outbox.event_delivery
            SET destination_url = NULL
            WHERE id = :delivery_id
            """
        ),
        {"delivery_id": delivery.id},
    )


@given(parsers.parse('the same routed Event has pending delivery "{destination_name}" to "{destination_url}"'))
def same_event_has_pending_delivery(
    ctx: TestContext,
    destination_name: str,
    destination_url: str,
) -> None:
    event = _state(ctx)["event"]

    if event is None:
        raise AssertionError("No routed Event has been registered.")

    delivery = ctx.factory.event_delivery(
        EventDeliveryRecord(
            event=event,
            destination_name=destination_name,
            destination_type="webhook",
            destination_url=destination_url,
            status="PENDING",
            attempt_count=0,
            last_error=None,
        )
    )

    _state(ctx)["deliveries"][destination_name] = delivery


@given("webhook deliveries will record successful calls")
def webhook_deliveries_will_record_successful_calls(ctx: TestContext, monkeypatch) -> None:
    def post_stub(url, json, headers, timeout):
        _state(ctx)["http_calls"] += 1
        _state(ctx)["last_http_url"] = url
        _state(ctx)["last_http_json"] = json
        return StubResponse(status_code=200)

    monkeypatch.setattr(httpx, "post", post_stub)


@when(parsers.parse("missing delivery id {delivery_id:d} is processed by the delivery worker"))
def missing_delivery_id_is_processed(ctx: TestContext, delivery_id: int) -> None:
    _state(ctx)["missing_delivery_error"] = None

    try:
        deliver_one_delivery(
            delivery_id=delivery_id,
            db=ctx.db_session,
        )
    except Exception as exc:
        _state(ctx)["missing_delivery_error"] = exc


@then(parsers.parse("webhook delivery should have been called {expected_count:d} times"))
def webhook_delivery_should_have_been_called_times(
    ctx: TestContext,
    expected_count: int,
) -> None:
    assert _state(ctx)["http_calls"] == expected_count


@then(parsers.parse('the last webhook call should target URL "{destination_url}"'))
def last_webhook_call_should_target_url(ctx: TestContext, destination_url: str) -> None:
    assert _state(ctx)["last_http_url"] == destination_url


@then(parsers.parse('the last webhook call payload should contain number "{field_name}" equal to {expected_value:g}'))
def last_webhook_call_payload_should_contain_number(
    ctx: TestContext,
    field_name: str,
    expected_value: float,
) -> None:
    assert _state(ctx)["last_http_json"][field_name] == expected_value


@then("missing delivery processing should not fail")
def missing_delivery_processing_should_not_fail(ctx: TestContext) -> None:
    assert _state(ctx)["missing_delivery_error"] is None
