from pytest_bdd import parsers
from pytest_bdd import then
from pytest_bdd import when

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


schema_create_pattern = parsers.parse(
    'schema version "{internal_version}" with client version "{client_version}" is created for event type "{event_type_code}" in project "{project_name}"'
)
schema_create_by_event_type_id_pattern = parsers.parse(
    'schema version "{internal_version}" with client version "{client_version}" is created for event type with id {event_type_id:d}'
)
schema_list_pattern = parsers.parse(
    'schemas are listed for event type "{event_type_code}" in project "{project_name}"'
)
schema_should_be_registered_pattern = parsers.parse(
    'schema version "{internal_version}" should be registered for event type "{event_type_code}"'
)
no_schema_should_be_registered_pattern = parsers.parse(
    'no schema version "{internal_version}" should be registered for event type "{event_type_code}"'
)
schema_should_be_active_pattern = parsers.parse(
    'schema version "{internal_version}" should be active for event type "{event_type_code}"'
)
schema_should_match_submitted_pattern = parsers.parse(
    'schema version "{internal_version}" should match the submitted JSON Schema for event type "{event_type_code}"'
)
response_contains_schema_version_pattern = parsers.parse(
    'the response should contain schema version "{internal_version}"'
)


def _schema_state(ctx: TestContext) -> dict:
    state = getattr(ctx, "schema_definition_state", None)

    if state is None:
        state = {"submitted_schemas": {}}
        setattr(ctx, "schema_definition_state", state)

    return state


def _json_schema_for(internal_version: str) -> dict:
    return {
        "type": "object",
        "properties": {
            "duration_seconds": {"type": "number"},
            "schema_version_marker": {"const": internal_version},
        },
        "required": ["duration_seconds"],
    }


@when(schema_create_pattern)
def schema_is_created(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    internal_version: str,
    client_version: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )

    _create_schema(
        ctx=ctx,
        event_type_id=event_type.id,
        event_type_code=event_type_code,
        internal_version=internal_version,
        client_version=client_version,
    )


@when(schema_create_by_event_type_id_pattern)
def schema_is_created_by_event_type_id(
    ctx: TestContext,
    event_type_id: int,
    internal_version: str,
    client_version: str,
) -> None:
    _create_schema(
        ctx=ctx,
        event_type_id=event_type_id,
        event_type_code=f"event-type-{event_type_id}",
        internal_version=internal_version,
        client_version=client_version,
    )


def _create_schema(
    ctx: TestContext,
    event_type_id: int,
    event_type_code: str,
    internal_version: str,
    client_version: str,
) -> None:
    json_schema = _json_schema_for(internal_version)

    _schema_state(ctx)["submitted_schemas"][
        (event_type_code, internal_version)
    ] = json_schema

    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type_id}/schemas",
        json={
            "json_version_client": client_version,
            "json_version_internal": internal_version,
            "json_schema": json_schema,
        },
        headers=ctx.request_headers or {},
    )


@when(schema_list_pattern)
def schemas_are_listed(
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
        f"/api/admin/event-types/{event_type.id}/schemas",
        headers=ctx.request_headers or {},
    )


@then(schema_should_be_registered_pattern)
def schema_should_be_registered(
    ctx: TestContext,
    step_registry: StepRegistry,
    event_type_code: str,
    internal_version: str,
) -> None:
    step_registry.schema_definition_assertion_for("exists")(
        ctx=ctx,
        event_type_code=event_type_code,
        version=internal_version,
    )


@then(no_schema_should_be_registered_pattern)
def no_schema_should_be_registered(
    ctx: TestContext,
    step_registry: StepRegistry,
    event_type_code: str,
    internal_version: str,
) -> None:
    step_registry.schema_definition_assertion_for("is absent")(
        ctx=ctx,
        event_type_code=event_type_code,
        version=internal_version,
    )


@then(schema_should_be_active_pattern)
def schema_should_be_active(
    ctx: TestContext,
    step_registry: StepRegistry,
    event_type_code: str,
    internal_version: str,
) -> None:
    step_registry.schema_definition_assertion_for("is active")(
        ctx=ctx,
        event_type_code=event_type_code,
        version=internal_version,
    )


@then(schema_should_match_submitted_pattern)
def schema_should_match_submitted_json_schema(
    ctx: TestContext,
    step_registry: StepRegistry,
    event_type_code: str,
    internal_version: str,
) -> None:
    submitted = _schema_state(ctx)["submitted_schemas"][
        (event_type_code, internal_version)
    ]

    step_registry.schema_definition_assertion_for("matches json schema")(
        ctx=ctx,
        event_type_code=event_type_code,
        version=internal_version,
        expected_json_schema=submitted,
    )


@then(response_contains_schema_version_pattern)
def response_should_contain_schema_version(
    ctx: TestContext,
    step_registry: StepRegistry,
    internal_version: str,
) -> None:
    step_registry.response_assertion_for("contains schema version")(
        ctx=ctx,
        version=internal_version,
    )


@then("the response should be an empty list")
def response_should_be_empty_list(
    ctx: TestContext,
    step_registry: StepRegistry,
) -> None:
    step_registry.response_assertion_for("is empty list")(ctx=ctx)
