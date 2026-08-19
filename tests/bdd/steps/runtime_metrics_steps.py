from datetime import UTC, datetime, timedelta

from pytest_bdd import given, parsers, then, when
from sqlalchemy import text

from tests.domain.record import (
    EventDeliveryRecord,
    EventRecord,
    EventTypeRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.context import TestContext


def _runtime_graph(ctx: TestContext):
    graph = getattr(ctx, "runtime_metrics_graph", None)
    if graph is None:
        project = ctx.seed.project_registered("runtime-metrics")
        event_type = ctx.factory.event_type(
            EventTypeRecord(
                project=project,
                code="runtime.event",
                name="Runtime event",
            )
        )
        schema = ctx.factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema={"type": "object"},
            )
        )
        graph = (project, event_type, schema)
        setattr(ctx, "runtime_metrics_graph", graph)
    return graph


def _create_event(ctx: TestContext, status: str):
    _, event_type, schema = _runtime_graph(ctx)
    return ctx.factory.event(
        EventRecord(
            event_type=event_type,
            schema_definition=schema,
            payload={},
            status=status,
        )
    )


@given("Events exist with the following statuses:")
def events_exist_with_statuses(ctx: TestContext, datatable: list[list[str]]) -> None:
    for status, count in datatable[1:]:
        for _ in range(int(count)):
            _create_event(ctx, status)


@given("Deliveries exist with the following states:")
def deliveries_exist_with_states(ctx: TestContext, datatable: list[list[str]]) -> None:
    for status, attempt_count in datatable[1:]:
        ctx.factory.event_delivery(
            EventDeliveryRecord(
                event=_create_event(ctx, "ROUTED"),
                status=status,
                attempt_count=int(attempt_count),
            )
        )


@given(parsers.parse("a received Event created {age:d} seconds ago"))
def received_event_created_ago(ctx: TestContext, age: int) -> None:
    event = _create_event(ctx, "RECEIVED")
    ctx.db_session.execute(
        text("UPDATE outbox.event SET created_at = :created_at WHERE id = :id"),
        {"created_at": datetime.now(UTC) - timedelta(seconds=age), "id": event.id},
    )


@given(parsers.parse("a pending Delivery created {age:d} seconds ago"))
def pending_delivery_created_ago(ctx: TestContext, age: int) -> None:
    delivery = ctx.factory.event_delivery(
        EventDeliveryRecord(event=_create_event(ctx, "ROUTED"), status="PENDING")
    )
    ctx.db_session.execute(
        text("UPDATE outbox.event_delivery SET created_at = :created_at WHERE id = :id"),
        {"created_at": datetime.now(UTC) - timedelta(seconds=age), "id": delivery.id},
    )


@given("a retryable dead letter with 4 attempts exists for runtime metrics")
def retryable_dead_letter_exists(ctx: TestContext) -> None:
    project, _, _ = _runtime_graph(ctx)
    user = ctx.seed.user_registered(
        email="runtime-owner@example.com",
        password="ValidPassword123!",
    )
    ctx.seed.project_member_registered(project=project, user=user, role="OWNER")
    delivery = ctx.factory.event_delivery(
        EventDeliveryRecord(
            event=_create_event(ctx, "ROUTED"),
            status="DEAD_LETTER",
            attempt_count=4,
            last_error="downstream unavailable",
        )
    )
    setattr(ctx, "runtime_dead_letter", (project.id, delivery.id))
    ctx.request_headers = ctx.auth.as_user(user)


@when("the runtime metrics summary is requested")
def runtime_metrics_summary_is_requested(ctx: TestContext) -> None:
    ctx.last_response = ctx.client.get("/api/runtime/metrics/summary")


@when("the runtime dead letter is retried")
def runtime_dead_letter_is_retried(ctx: TestContext) -> None:
    project_id, delivery_id = getattr(ctx, "runtime_dead_letter")
    ctx.last_response = ctx.client.post(
        f"/api/admin/projects/{project_id}/dead-letters/{delivery_id}/retry",
        headers=ctx.request_headers or {},
    )


@then("the runtime summary should contain:")
def runtime_summary_should_contain(ctx: TestContext, datatable: list[list[str]]) -> None:
    assert ctx.last_response is not None
    payload = ctx.last_response.json()
    for field, raw_value in datatable[1:]:
        expected = None if raw_value == "null" else int(raw_value)
        assert payload[field] == expected, field


@then(parsers.parse("the oldest received Event age should be at least {age:d} seconds"))
def oldest_received_event_age(ctx: TestContext, age: int) -> None:
    assert ctx.last_response.json()["oldest_received_age_seconds"] >= age


@then(parsers.parse("the oldest pending Delivery age should be at least {age:d} seconds"))
def oldest_pending_delivery_age(ctx: TestContext, age: int) -> None:
    assert ctx.last_response.json()["oldest_pending_delivery_age_seconds"] >= age
