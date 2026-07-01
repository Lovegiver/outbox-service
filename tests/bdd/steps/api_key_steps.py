from uuid import uuid4

from pytest_bdd import given
from pytest_bdd import parsers
from pytest_bdd import then
from pytest_bdd import when

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


api_key_create_pattern = parsers.parse(
    'API key "{api_key_name}" is created for project "{project_name}"'
)
api_key_list_pattern = parsers.parse(
    'API keys are listed for project "{project_name}"'
)
api_key_revoke_pattern = parsers.parse(
    'API key "{api_key_name}" is revoked for project "{project_name}"'
)
api_key_revoke_by_id_pattern = parsers.parse(
    'API key with id {api_key_id:d} is revoked for project "{project_name}"'
)
api_key_rotate_pattern = parsers.parse(
    'API key "{api_key_name}" is rotated for project "{project_name}"'
)
api_key_should_be_active_pattern = parsers.parse(
    'API key "{api_key_name}" should be active for project "{project_name}"'
)
api_key_should_be_revoked_pattern = parsers.parse(
    'API key "{api_key_name}" should be revoked for project "{project_name}"'
)
no_api_key_should_be_registered_pattern = parsers.parse(
    'no API key should be registered with name "{api_key_name}" for project "{project_name}"'
)
ingestible_event_type_pattern = parsers.parse(
    'project "{project_name}" has ingestible event type "{event_type_code}"'
)
event_ingested_with_named_key_pattern = parsers.parse(
    'an event is ingested for project "{project_name}" and event type "{event_type_code}" using API key "{api_key_name}"'
)
event_ingested_with_previous_key_pattern = parsers.parse(
    'an event is ingested for project "{project_name}" and event type "{event_type_code}" using the previous API key "{api_key_name}"'
)
event_ingested_with_latest_key_pattern = parsers.parse(
    'an event is ingested for project "{project_name}" and event type "{event_type_code}" using the latest API key'
)
event_should_be_registered_pattern = parsers.parse(
    'an event should be registered for project "{project_name}" and event type "{event_type_code}"'
)
response_not_expose_secret_pattern = parsers.parse(
    'the response should not expose the API key secret for "{api_key_name}"'
)
response_contains_api_key_pattern = parsers.parse(
    'the response should contain API key "{api_key_name}"'
)
latest_api_key_active_pattern = parsers.parse(
    'the latest API key should be active for project "{project_name}"'
)


def _api_key_state(ctx: TestContext) -> dict:
    state = getattr(ctx, "api_key_state", None)

    if state is None:
        state = {
            "ids_by_name": {},
            "secrets_by_name": {},
            "previous_secrets_by_name": {},
            "latest_id": None,
            "latest_secret": None,
            "last_ingested_event_uuid": None,
        }
        setattr(ctx, "api_key_state", state)

    return state


@given(ingestible_event_type_pattern)
def ingestible_event_type_exists(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    ctx.seed.event_type_with_schema(
        project=project,
        code=event_type_code,
        name=event_type_code,
        json_schema={
            "type": "object",
            "properties": {
                "duration_seconds": {"type": "number"},
            },
            "required": ["duration_seconds"],
        },
    )


@when(api_key_create_pattern)
def api_key_is_created(
    ctx: TestContext,
    api_key_name: str,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    ctx.last_response = ctx.client.post(
        f"/api/admin/projects/{project.id}/api-keys",
        json={"name": api_key_name},
        headers=ctx.request_headers or {},
    )

    if ctx.last_response.status_code == 201:
        payload = ctx.last_response.json()
        state = _api_key_state(ctx)
        state["ids_by_name"][api_key_name] = payload["id"]
        state["secrets_by_name"][api_key_name] = payload["api_key"]
        state["latest_id"] = payload["id"]
        state["latest_secret"] = payload["api_key"]


@when(api_key_list_pattern)
def api_keys_are_listed(
    ctx: TestContext,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    ctx.last_response = ctx.client.get(
        f"/api/admin/projects/{project.id}/api-keys",
        headers=ctx.request_headers or {},
    )


@when(api_key_revoke_pattern)
def api_key_is_revoked(
    ctx: TestContext,
    api_key_name: str,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    api_key_id = _api_key_state(ctx)["ids_by_name"][api_key_name]

    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project.id}/api-keys/{api_key_id}/revoke",
        headers=ctx.request_headers or {},
    )


@when(api_key_revoke_by_id_pattern)
def api_key_id_is_revoked(
    ctx: TestContext,
    api_key_id: int,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    ctx.last_response = ctx.client.patch(
        f"/api/admin/projects/{project.id}/api-keys/{api_key_id}/revoke",
        headers=ctx.request_headers or {},
    )


@when(api_key_rotate_pattern)
def api_key_is_rotated(
    ctx: TestContext,
    api_key_name: str,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    state = _api_key_state(ctx)
    api_key_id = state["ids_by_name"][api_key_name]

    state["previous_secrets_by_name"][api_key_name] = state["secrets_by_name"][api_key_name]

    ctx.last_response = ctx.client.post(
        f"/api/admin/projects/{project.id}/api-keys/{api_key_id}/rotate",
        headers=ctx.request_headers or {},
    )

    if ctx.last_response.status_code == 201:
        payload = ctx.last_response.json()
        rotated_name = payload["name"]
        state["ids_by_name"][rotated_name] = payload["id"]
        state["secrets_by_name"][rotated_name] = payload["api_key"]
        state["latest_id"] = payload["id"]
        state["latest_secret"] = payload["api_key"]


@when(event_ingested_with_named_key_pattern)
def event_is_ingested_with_named_api_key(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    api_key_name: str,
) -> None:
    secret = _api_key_state(ctx)["secrets_by_name"][api_key_name]
    _ingest_event(ctx, project_name, event_type_code, secret)


@when(event_ingested_with_previous_key_pattern)
def event_is_ingested_with_previous_api_key(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    api_key_name: str,
) -> None:
    secret = _api_key_state(ctx)["previous_secrets_by_name"][api_key_name]
    _ingest_event(ctx, project_name, event_type_code, secret)


@when(event_ingested_with_latest_key_pattern)
def event_is_ingested_with_latest_api_key(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    secret = _api_key_state(ctx)["latest_secret"]
    _ingest_event(ctx, project_name, event_type_code, secret)


def _ingest_event(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    api_key_secret: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )
    event_uuid = str(uuid4())

    _api_key_state(ctx)["last_ingested_event_uuid"] = event_uuid

    ctx.last_response = ctx.client.post(
        "/events",
        json={
            "project_id": project.id,
            "event_type_id": event_type.id,
            "json_version_internal": "1.0",
            "event_uuid": event_uuid,
            "payload": {"duration_seconds": 12.3},
        },
        headers={"X-API-Key": api_key_secret},
    )


@then("the response should contain an API key secret")
def response_should_contain_api_key_secret(
    ctx: TestContext,
    step_registry: StepRegistry,
) -> None:
    step_registry.response_assertion_for("contains api key secret")(ctx=ctx)


@then(response_not_expose_secret_pattern)
def response_should_not_expose_named_api_key_secret(
    ctx: TestContext,
    step_registry: StepRegistry,
    api_key_name: str,
) -> None:
    step_registry.response_assertion_for("does not expose api key secret")(
        ctx=ctx,
        api_key_name=api_key_name,
    )


@then("the listed API keys should not expose complete secrets")
def listed_api_keys_should_not_expose_complete_secrets(
    ctx: TestContext,
    step_registry: StepRegistry,
) -> None:
    step_registry.response_assertion_for("does not expose complete api key secrets")(
        ctx=ctx,
    )


@then(response_contains_api_key_pattern)
def response_should_contain_api_key(
    ctx: TestContext,
    step_registry: StepRegistry,
    api_key_name: str,
) -> None:
    step_registry.response_assertion_for("contains api key")(
        ctx=ctx,
        api_key_name=api_key_name,
    )


@then(api_key_should_be_active_pattern)
def api_key_should_be_active(
    ctx: TestContext,
    step_registry: StepRegistry,
    api_key_name: str,
    project_name: str,
) -> None:
    step_registry.api_key_assertion_for("is active")(
        ctx=ctx,
        project_name=project_name,
        api_key_name=api_key_name,
    )


@then(api_key_should_be_revoked_pattern)
def api_key_should_be_revoked(
    ctx: TestContext,
    step_registry: StepRegistry,
    api_key_name: str,
    project_name: str,
) -> None:
    step_registry.api_key_assertion_for("is revoked")(
        ctx=ctx,
        project_name=project_name,
        api_key_name=api_key_name,
    )


@then(latest_api_key_active_pattern)
def latest_api_key_should_be_active(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
) -> None:
    step_registry.api_key_assertion_for("latest is active")(
        ctx=ctx,
        project_name=project_name,
    )


@then(no_api_key_should_be_registered_pattern)
def no_api_key_should_be_registered(
    ctx: TestContext,
    step_registry: StepRegistry,
    api_key_name: str,
    project_name: str,
) -> None:
    step_registry.api_key_assertion_for("is absent")(
        ctx=ctx,
        project_name=project_name,
        api_key_name=api_key_name,
    )


@then(event_should_be_registered_pattern)
def event_should_be_registered(
    ctx: TestContext,
    step_registry: StepRegistry,
    project_name: str,
    event_type_code: str,
) -> None:
    step_registry.event_assertion_for("last ingested event exists")(
        ctx=ctx,
        project_name=project_name,
        event_type_code=event_type_code,
    )
