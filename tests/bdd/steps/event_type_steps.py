from pytest_bdd import given
from pytest_bdd import parsers
from pytest_bdd import then
from pytest_bdd import when

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


event_type_seed_pattern = parsers.parse(
    'project "{project_name}" has event type "{event_type_code}" named "{event_type_name}"'
)
event_type_create_pattern = parsers.parse(
    'event type "{event_type_code}" is created in project "{project_name}" with name "{event_type_name}"'
)
event_type_create_by_project_id_pattern = parsers.parse(
    'event type "{event_type_code}" is created in project with id {project_id:d} with name "{event_type_name}"'
)
event_types_list_pattern = parsers.parse(
    'event types are listed for project "{project_name}"'
)
event_type_request_pattern = parsers.parse(
    'event type "{event_type_code}" from project "{project_name}" is requested'
)
event_type_should_be_registered_pattern = parsers.parse(
    'event type "{event_type_code}" should be registered in project "{project_name}"'
)
no_event_type_should_be_registered_pattern = parsers.parse(
    'no event type "{event_type_code}" should be registered in project "{project_name}"'
)
response_contains_event_type_pattern = parsers.parse(
    'the response should contain event type "{event_type_code}"'
)
response_identifies_event_type_pattern = parsers.parse(
    'the response should identify event type "{event_type_code}"'
)


@given(event_type_seed_pattern)
def project_has_event_type(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    event_type_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    ctx.seed.event_type_registered(
        project=project,
        code=event_type_code,
        name=event_type_name,
    )


@when(event_type_create_pattern)
def event_type_is_created(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    event_type_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    _create_event_type(
        ctx=ctx,
        project_id=project.id,
        event_type_code=event_type_code,
        event_type_name=event_type_name,
    )


@when(event_type_create_by_project_id_pattern)
def event_type_is_created_by_project_id(
    ctx: TestContext,
    project_id: int,
    event_type_code: str,
    event_type_name: str,
) -> None:
    _create_event_type(
        ctx=ctx,
        project_id=project_id,
        event_type_code=event_type_code,
        event_type_name=event_type_name,
    )


def _create_event_type(
    ctx: TestContext,
    project_id: int,
    event_type_code: str,
    event_type_name: str,
) -> None:
    ctx.last_response = ctx.client.post(
        "/api/admin/event-types",
        json={
            "project_id": project_id,
            "code": event_type_code,
            "name": event_type_name,
            "description": f"BDD event type {event_type_name}",
        },
        headers=ctx.request_headers or {},
    )


@when(event_types_list_pattern)
def event_types_are_listed(
    ctx: TestContext,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    ctx.last_response = ctx.client.get(
        f"/api/admin/event-types/by-project/{project.id}",
        headers=ctx.request_headers or {},
    )


@when(event_type_request_pattern)
def event_type_is_requested(
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
        f"/api/admin/event-types/{event_type.id}",
        headers=ctx.request_headers or {},
    )


@then(event_type_should_be_registered_pattern)
def event_type_should_be_registered(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
    event_type_code: str,
) -> None:
    step_registry.event_type_assertion_for("exists")(
        ctx=ctx,
        project_name=project_name,
        event_type_code=event_type_code,
    )


@then(no_event_type_should_be_registered_pattern)
def no_event_type_should_be_registered(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
    event_type_code: str,
) -> None:
    step_registry.event_type_assertion_for("is absent")(
        ctx=ctx,
        project_name=project_name,
        event_type_code=event_type_code,
    )


@then(response_contains_event_type_pattern)
def response_should_contain_event_type(
    ctx: TestContext,
    step_registry: StepRegistry,
    event_type_code: str,
) -> None:
    step_registry.response_assertion_for("contains event type")(
        ctx=ctx,
        event_type_code=event_type_code,
    )


@then(response_identifies_event_type_pattern)
def response_should_identify_event_type(
    ctx: TestContext,
    step_registry: StepRegistry,
    event_type_code: str,
) -> None:
    step_registry.response_assertion_for("identifies event type")(
        ctx=ctx,
        event_type_code=event_type_code,
    )
