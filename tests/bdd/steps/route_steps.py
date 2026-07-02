from pytest_bdd import given
from pytest_bdd import parsers
from pytest_bdd import then
from pytest_bdd import when

from app.worker import route_received_events
from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


route_seed_pattern = parsers.parse(
    'event type "{event_type_code}" in project "{project_name}" has route "{destination_name}" with routing key "{routing_key}" and URL "{destination_url}"'
)
route_create_pattern = parsers.parse(
    'route "{destination_name}" with routing key "{routing_key}" and URL "{destination_url}" is created for event type "{event_type_code}" in project "{project_name}"'
)
route_create_by_event_type_id_pattern = parsers.parse(
    'route "{destination_name}" with routing key "{routing_key}" and URL "{destination_url}" is created for event type with id {event_type_id:d}'
)
routes_list_pattern = parsers.parse(
    'routes are listed for event type "{event_type_code}" in project "{project_name}"'
)
route_update_pattern = parsers.parse(
    'route "{destination_name}" for event type "{event_type_code}" in project "{project_name}" is updated to routing key "{routing_key}" and URL "{destination_url}"'
)
route_update_missing_pattern = parsers.parse(
    'route with id {route_id:d} for event type "{event_type_code}" in project "{project_name}" is updated to URL "{destination_url}"'
)
route_should_be_active_pattern = parsers.parse(
    'route "{destination_name}" should be active for event type "{event_type_code}" in project "{project_name}"'
)
route_should_target_url_pattern = parsers.parse(
    'route "{destination_name}" should target URL "{destination_url}" for event type "{event_type_code}" in project "{project_name}"'
)
no_route_should_be_registered_pattern = parsers.parse(
    'no route "{destination_name}" should be registered for event type "{event_type_code}" in project "{project_name}"'
)
response_contains_route_pattern = parsers.parse(
    'the response should contain route "{destination_name}"'
)
received_event_pattern = parsers.parse(
    'project "{project_name}" has a received event for event type "{event_type_code}"'
)
delivery_created_pattern = parsers.parse(
    'a delivery should be created for destination "{destination_name}"'
)
delivery_created_with_url_pattern = parsers.parse(
    'a delivery should be created for destination "{destination_name}" with URL "{destination_url}"'
)


def _route_state(ctx: TestContext) -> dict:
    state = getattr(ctx, "route_state", None)

    if state is None:
        state = {"last_event": None}
        setattr(ctx, "route_state", state)

    return state


@given(route_seed_pattern)
def event_type_has_route(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    destination_name: str,
    routing_key: str,
    destination_url: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )

    ctx.seed.route_registered(
        event_type=event_type,
        routing_key=routing_key,
        destination_name=destination_name,
        destination_url=destination_url,
    )


@given(received_event_pattern)
def project_has_received_event(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )

    event = ctx.seed.received_event_registered(
        event_type=event_type,
        payload={"duration_seconds": 12.3},
    )

    _route_state(ctx)["last_event"] = event


@when(route_create_pattern)
def route_is_created(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    destination_name: str,
    routing_key: str,
    destination_url: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )

    _create_route(ctx, event_type.id, destination_name, routing_key, destination_url)


@when(route_create_by_event_type_id_pattern)
def route_is_created_by_event_type_id(
    ctx: TestContext,
    event_type_id: int,
    destination_name: str,
    routing_key: str,
    destination_url: str,
) -> None:
    _create_route(ctx, event_type_id, destination_name, routing_key, destination_url)


def _create_route(
    ctx: TestContext,
    event_type_id: int,
    destination_name: str,
    routing_key: str,
    destination_url: str,
) -> None:
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type_id}/routes",
        json={
            "routing_key": routing_key,
            "destination_name": destination_name,
            "destination_url": destination_url,
        },
        headers=ctx.request_headers or {},
    )


@when(routes_list_pattern)
def routes_are_listed(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )

    ctx.last_response = ctx.client.get(
        f"/api/admin/event-types/{event_type.id}/routes",
        headers=ctx.request_headers or {},
    )


@when(route_update_pattern)
def route_is_updated(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    destination_name: str,
    routing_key: str,
    destination_url: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )
    route_id = ctx.probe.route_definition.get_id_by_event_type_and_destination(
        event_type=event_type,
        destination_name=destination_name,
    )

    _update_route(
        ctx=ctx,
        event_type_id=event_type.id,
        route_id=route_id,
        routing_key=routing_key,
        destination_name=destination_name,
        destination_url=destination_url,
    )


@when(route_update_missing_pattern)
def missing_route_is_updated(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    route_id: int,
    destination_url: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )

    _update_route(
        ctx=ctx,
        event_type_id=event_type.id,
        route_id=route_id,
        routing_key="default",
        destination_name="missing-route",
        destination_url=destination_url,
    )


def _update_route(
    ctx: TestContext,
    event_type_id: int,
    route_id: int,
    routing_key: str,
    destination_name: str,
    destination_url: str,
) -> None:
    ctx.last_response = ctx.client.patch(
        f"/api/admin/event-types/{event_type_id}/routes/{route_id}",
        json={
            "routing_key": routing_key,
            "destination_name": destination_name,
            "destination_url": destination_url,
        },
        headers=ctx.request_headers or {},
    )


@when("received events are routed by the worker")
def received_events_are_routed_by_worker(ctx: TestContext) -> None:
    route_received_events(ctx.db_session)


@then(route_should_be_active_pattern)
def route_should_be_active(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
    event_type_code: str,
    destination_name: str,
) -> None:
    step_registry.route_definition_assertion_for("is active")(
        ctx=ctx,
        project_name=project_name,
        event_type_code=event_type_code,
        destination_name=destination_name,
    )


@then(route_should_target_url_pattern)
def route_should_target_url(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
    event_type_code: str,
    destination_name: str,
    destination_url: str,
) -> None:
    step_registry.route_definition_assertion_for("targets url")(
        ctx=ctx,
        project_name=project_name,
        event_type_code=event_type_code,
        destination_name=destination_name,
        destination_url=destination_url,
    )


@then(no_route_should_be_registered_pattern)
def no_route_should_be_registered(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
    event_type_code: str,
    destination_name: str,
) -> None:
    step_registry.route_definition_assertion_for("is absent")(
        ctx=ctx,
        project_name=project_name,
        event_type_code=event_type_code,
        destination_name=destination_name,
    )


@then(response_contains_route_pattern)
def response_should_contain_route(
    ctx: TestContext,
    step_registry: StepRegistry,
    destination_name: str,
) -> None:
    step_registry.response_assertion_for("contains route")(
        ctx=ctx,
        destination_name=destination_name,
    )


@then(delivery_created_pattern)
def delivery_should_be_created(
    ctx: TestContext,
    step_registry: StepRegistry,
    destination_name: str,
) -> None:
    event = _route_state(ctx)["last_event"]

    step_registry.event_delivery_assertion_for("exists for event and destination")(
        ctx=ctx,
        event=event,
        destination_name=destination_name,
    )


@then(delivery_created_with_url_pattern)
def delivery_should_be_created_with_url(
    ctx: TestContext,
    step_registry: StepRegistry,
    destination_name: str,
    destination_url: str,
) -> None:
    event = _route_state(ctx)["last_event"]

    step_registry.event_delivery_assertion_for("exists for event destination and url")(
        ctx=ctx,
        event=event,
        destination_name=destination_name,
        destination_url=destination_url,
    )
