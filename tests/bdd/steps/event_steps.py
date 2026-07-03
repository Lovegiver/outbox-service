from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from pytest_bdd import given
from pytest_bdd import parsers
from pytest_bdd import then
from pytest_bdd import when

from app.services.api_key_service import ApiKeyService
from tests.domain.record import ApiKeyRecord
from tests.domain.record import SchemaDefinitionRecord
from tests.infrastructure.context import TestContext


RESOURCE_ROOT = Path(__file__).resolve().parents[1] / "resources"
EVENT_RESOURCE_ROOT = RESOURCE_ROOT / "events"
SCHEMA_RESOURCE_ROOT = RESOURCE_ROOT / "schemas"


active_schema_pattern = parsers.parse(
    'event type "{event_type_code}" in project "{project_name}" has active schema "{schema_file}"'
)
active_api_key_pattern = parsers.parse(
    'project "{project_name}" has active API key "{api_key_name}"'
)
revoked_api_key_pattern = parsers.parse(
    'project "{project_name}" has revoked API key "{api_key_name}"'
)
submit_event_pattern = parsers.parse(
    'event "{event_type_code}" is submitted for project "{project_name}" with payload "{payload_file}"'
)
submit_event_without_api_key_pattern = parsers.parse(
    'event "{event_type_code}" is submitted for project "{project_name}" with payload "{payload_file}" without API key'
)
submit_event_invalid_api_key_pattern = parsers.parse(
    'event "{event_type_code}" is submitted for project "{project_name}" with payload "{payload_file}" and invalid API key'
)
submit_event_with_ids_pattern = parsers.parse(
    'event "{event_type_code}" is submitted for project "{project_name}" with payload "{payload_file}", event UUID "{event_uuid}" and correlation ID "{correlation_id}"'
)
event_persisted_pattern = parsers.parse(
    'an event should be persisted for project "{project_name}" and event type "{event_type_code}"'
)
no_event_persisted_pattern = parsers.parse(
    'no event should be persisted for project "{project_name}" and event type "{event_type_code}"'
)
persisted_event_status_pattern = parsers.parse(
    'the persisted event should have status "{status}"'
)
persisted_schema_version_pattern = parsers.parse(
    'the persisted event should use schema version "{schema_version}"'
)
event_uuid_persisted_pattern = parsers.parse(
    'event UUID "{event_uuid}" should be persisted'
)
correlation_id_persisted_pattern = parsers.parse(
    'correlation ID "{correlation_id}" should be persisted'
)


def _event_state(ctx: TestContext) -> dict:
    state = getattr(ctx, "event_state", None)

    if state is None:
        state = {
            "api_keys": {},
            "last_event_id": None,
            "last_event_uuid": None,
        }
        setattr(ctx, "event_state", state)

    return state


def _load_json(root: Path, filename: str) -> dict:
    return json.loads((root / filename).read_text(encoding="utf-8"))


@given(active_schema_pattern)
def event_type_has_active_schema(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    schema_file: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )

    ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=event_type,
            json_schema=_load_json(SCHEMA_RESOURCE_ROOT, schema_file),
            json_version_internal="1.0",
            json_version_client="v1",
            is_active=True,
        )
    )


@given(active_api_key_pattern)
def project_has_active_api_key(
    ctx: TestContext,
    project_name: str,
    api_key_name: str,
) -> None:
    _register_api_key(ctx, project_name, api_key_name, True)


@given(revoked_api_key_pattern)
def project_has_revoked_api_key(
    ctx: TestContext,
    project_name: str,
    api_key_name: str,
) -> None:
    _register_api_key(ctx, project_name, api_key_name, False)


def _register_api_key(
    ctx: TestContext,
    project_name: str,
    api_key_name: str,
    is_active: bool,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    plain_key = f"obx_ingest_{project.id}_{api_key_name}_bdd_secret"
    key_prefix = plain_key[:32]
    key_hash = ApiKeyService.hash_key(plain_key)

    ctx.factory.api_key(
        ApiKeyRecord(
            project=project,
            name=api_key_name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            is_active=is_active,
        )
    )

    _event_state(ctx)["api_keys"][project_name] = plain_key


@when(submit_event_pattern)
def submit_event(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    payload_file: str,
) -> None:
    api_key = _event_state(ctx)["api_keys"][project_name]
    _submit_event(ctx, project_name, event_type_code, payload_file, api_key, None, None)


@when(submit_event_without_api_key_pattern)
def submit_event_without_api_key(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    payload_file: str,
) -> None:
    _submit_event(ctx, project_name, event_type_code, payload_file, None, None, None)


@when(submit_event_invalid_api_key_pattern)
def submit_event_with_invalid_api_key(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    payload_file: str,
) -> None:
    _submit_event(ctx, project_name, event_type_code, payload_file, "invalid-api-key", None, None)


@when(submit_event_with_ids_pattern)
def submit_event_with_identifiers(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    payload_file: str,
    event_uuid: str,
    correlation_id: str,
) -> None:
    api_key = _event_state(ctx)["api_keys"][project_name]
    _submit_event(ctx, project_name, event_type_code, payload_file, api_key, event_uuid, correlation_id)


def _submit_event(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    payload_file: str,
    api_key: str | None,
    event_uuid: str | None,
    correlation_id: str | None,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )

    body = {
        "project_id": project.id,
        "event_type_id": event_type.id,
        "json_version_internal": "1.0",
        "payload": _load_json(EVENT_RESOURCE_ROOT, payload_file),
    }

    if event_uuid is not None:
        body["event_uuid"] = event_uuid

    if correlation_id is not None:
        body["correlation_id"] = correlation_id

    headers = {}

    if api_key is not None:
        headers["X-API-Key"] = api_key

    ctx.last_response = ctx.client.post("/events", json=body, headers=headers)

    if ctx.last_response.status_code == 200:
        payload = ctx.last_response.json()
        _event_state(ctx)["last_event_id"] = payload["id"]
        _event_state(ctx)["last_event_uuid"] = payload["event_uuid"]


@then(event_persisted_pattern)
def event_should_be_persisted(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(project=project, code=event_type_code)

    assert ctx.probe.event.exists_by_project_and_event_type(project=project, event_type=event_type)


@then(no_event_persisted_pattern)
def no_event_should_be_persisted(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(project=project, code=event_type_code)

    assert not ctx.probe.event.exists_by_project_and_event_type(project=project, event_type=event_type)


@then(persisted_event_status_pattern)
def persisted_event_should_have_status(ctx: TestContext, status: str) -> None:
    event_id = _event_state(ctx)["last_event_id"]
    assert ctx.probe.event.status_by_id(event_id) == status


@then(persisted_schema_version_pattern)
def persisted_event_should_use_schema_version(ctx: TestContext, schema_version: str) -> None:
    event_id = _event_state(ctx)["last_event_id"]
    assert ctx.probe.event.schema_version_by_id(event_id) == schema_version


@then("the response should contain an event UUID")
def response_should_contain_event_uuid(ctx: TestContext) -> None:
    assert ctx.last_response is not None
    UUID(ctx.last_response.json()["event_uuid"])


@then(event_uuid_persisted_pattern)
def event_uuid_should_be_persisted(ctx: TestContext, event_uuid: str) -> None:
    assert ctx.probe.event.exists_by_uuid(event_uuid)


@then(correlation_id_persisted_pattern)
def correlation_id_should_be_persisted(ctx: TestContext, correlation_id: str) -> None:
    assert ctx.probe.event.exists_by_correlation_id(correlation_id)


@then("no delivery should be created for the persisted event")
def no_delivery_should_be_created_for_persisted_event(ctx: TestContext) -> None:
    event_id = _event_state(ctx)["last_event_id"]
    assert not ctx.probe.event_delivery.exists_by_event_id(event_id)
