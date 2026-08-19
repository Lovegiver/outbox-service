from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from app.worker import route_received_events
from tests.infrastructure.context import TestContext


received_event_pattern = parsers.parse('project "{project_name}" has a received Event of type "{event_type_code}"')
event_status_pattern = parsers.parse('the received Event should have status "{status}"')
event_delivery_count_pattern = parsers.parse("the received Event should have {delivery_count:d} delivery")
event_delivery_count_plural_pattern = parsers.parse("the received Event should have {delivery_count:d} deliveries")
delivery_created_pattern = parsers.parse('delivery "{destination_name}" should be created for the received Event')
delivery_status_pattern = parsers.parse('delivery "{destination_name}" should have status "{status}"')
delivery_destination_type_pattern = parsers.parse('delivery "{destination_name}" should have destination type "{destination_type}"')
delivery_url_pattern = parsers.parse('delivery "{destination_name}" should target URL "{destination_url}"')
delivery_attempt_count_pattern = parsers.parse('delivery "{destination_name}" should have attempt count {attempt_count:d}')
delivery_no_last_error_pattern = parsers.parse('delivery "{destination_name}" should have no last error')
delivery_linked_pattern = parsers.parse('delivery "{destination_name}" should be linked to the received Event')


def _state(ctx: TestContext) -> dict:
    state = getattr(ctx, "event_delivery_state", None)
    if state is None:
        state = {"event": None}
        setattr(ctx, "event_delivery_state", state)
    return state


def _event(ctx: TestContext):
    event = _state(ctx)["event"]
    if event is None:
        raise AssertionError("No received Event has been registered.")
    return event


@given(received_event_pattern)
def project_has_received_event(ctx: TestContext, project_name: str, event_type_code: str) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(project=project, code=event_type_code)
    event = ctx.seed.received_event_registered(event_type=event_type, payload={"duration_seconds": 12.3})
    _state(ctx)["event"] = event


@when("received Events are routed into deliveries")
def received_events_are_routed_into_deliveries(ctx: TestContext) -> None:
    route_received_events(ctx.db_session)


@then(event_status_pattern)
def received_event_should_have_status(ctx: TestContext, status: str) -> None:
    assert ctx.probe.event.status_by_id(_event(ctx).id) == status


@then(event_delivery_count_pattern)
@then(event_delivery_count_plural_pattern)
def received_event_should_have_delivery_count(ctx: TestContext, delivery_count: int) -> None:
    assert ctx.probe.event_delivery.count_by_event_id(_event(ctx).id) == delivery_count


@then(delivery_created_pattern)
def delivery_should_be_created(ctx: TestContext, destination_name: str) -> None:
    assert ctx.probe.event_delivery.exists_by_event_and_destination(event=_event(ctx), destination_name=destination_name)


@then(delivery_status_pattern)
def delivery_should_have_status(ctx: TestContext, destination_name: str, status: str) -> None:
    assert ctx.probe.event_delivery.status_by_event_and_destination(_event(ctx), destination_name) == status


@then(delivery_destination_type_pattern)
def delivery_should_have_destination_type(ctx: TestContext, destination_name: str, destination_type: str) -> None:
    assert ctx.probe.event_delivery.destination_type_by_event_and_destination(_event(ctx), destination_name) == destination_type


@then(delivery_url_pattern)
def delivery_should_target_url(ctx: TestContext, destination_name: str, destination_url: str) -> None:
    assert ctx.probe.event_delivery.destination_url_by_event_and_destination(_event(ctx), destination_name) == destination_url


@then(delivery_attempt_count_pattern)
def delivery_should_have_attempt_count(ctx: TestContext, destination_name: str, attempt_count: int) -> None:
    assert ctx.probe.event_delivery.attempt_count_by_event_and_destination(_event(ctx), destination_name) == attempt_count


@then(delivery_no_last_error_pattern)
def delivery_should_have_no_last_error(ctx: TestContext, destination_name: str) -> None:
    assert ctx.probe.event_delivery.last_error_by_event_and_destination(_event(ctx), destination_name) is None


@then(delivery_linked_pattern)
def delivery_should_be_linked_to_event(ctx: TestContext, destination_name: str) -> None:
    event = _event(ctx)
    assert ctx.probe.event_delivery.event_id_by_event_and_destination(event, destination_name) == event.id
