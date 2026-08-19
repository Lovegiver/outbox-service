from __future__ import annotations

from typing import Any
from pytest_bdd import given, parsers, then, when
from tests.domain.record import EventTypeRecord, MetricDefinitionRecord, ProjectMemberRecord, ProjectRecord, UserAccountRecord
from tests.infrastructure.context import TestContext

project_member_pattern = parsers.parse('project "{project_name}" has user "{email}" with role "{role}"')
user_exists_pattern = parsers.parse('user "{email}" exists')
admin_user_exists_pattern = parsers.parse('user "{email}" exists with global role "{role}"')
event_type_pattern = parsers.parse('project "{project_name}" has event type "{event_type_code}" named "{event_type_name}"')
metric_create_pattern = parsers.parse('metric definition "{metric_code}" named "{metric_name}" is created for event type "{event_type_code}" in project "{project_name}"')
metric_create_unknown_event_type_pattern = parsers.parse('metric definition "{metric_code}" named "{metric_name}" is created for unknown event type id {event_type_id:d}')
metric_exists_pattern = parsers.parse('metric definition "{metric_code}" exists for event type "{event_type_code}" in project "{project_name}"')
metric_should_be_registered_pattern = parsers.parse('metric definition "{metric_code}" should be registered for event type "{event_type_code}" in project "{project_name}"')
metric_should_not_be_registered_pattern = parsers.parse('metric definition "{metric_code}" should not be registered for event type "{event_type_code}" in project "{project_name}"')
metric_should_be_active_pattern = parsers.parse('metric definition "{metric_code}" should be active for event type "{event_type_code}" in project "{project_name}"')
metric_list_pattern = parsers.parse('metric definitions are listed for event type "{event_type_code}" in project "{project_name}"')
response_contains_metric_pattern = parsers.parse('the response should contain metric definition "{metric_code}"')

def _state(ctx: TestContext) -> dict[str, Any]:
    state = getattr(ctx, "metric_definition_state", None)
    if state is None:
        state = {"projects": {}, "users": {}, "event_types": {}}
        setattr(ctx, "metric_definition_state", state)
    return state

def _get_or_create_project(ctx: TestContext, project_name: str):
    state = _state(ctx)
    if project_name not in state["projects"]:
        state["projects"][project_name] = ctx.factory.project(ProjectRecord(name=project_name))
    return state["projects"][project_name]

def _get_or_create_user(ctx: TestContext, email: str, role: str = "USER"):
    state = _state(ctx)
    if email not in state["users"]:
        state["users"][email] = ctx.factory.user_account(UserAccountRecord(email=email, role=role))
    return state["users"][email]

def _event_type_key(project_name: str, event_type_code: str) -> str:
    return f"{project_name}:{event_type_code}"

def _get_event_type(ctx: TestContext, project_name: str, event_type_code: str):
    key = _event_type_key(project_name, event_type_code)
    event_type = _state(ctx)["event_types"].get(key)
    if event_type is None:
        project = _get_or_create_project(ctx, project_name)
        event_type = ctx.probe.event_type.get_by_project_and_code(project=project, code=event_type_code)
        _state(ctx)["event_types"][key] = event_type
    return event_type

@given(project_member_pattern)
def project_has_user_with_role(ctx: TestContext, project_name: str, email: str, role: str) -> None:
    project = _get_or_create_project(ctx, project_name)
    user = _get_or_create_user(ctx, email)
    ctx.factory.project_member(ProjectMemberRecord(project=project, user=user, role=role))

@given(user_exists_pattern)
def user_exists(ctx: TestContext, email: str) -> None:
    _get_or_create_user(ctx, email)

@given(admin_user_exists_pattern)
def user_exists_with_global_role(ctx: TestContext, email: str, role: str) -> None:
    _get_or_create_user(ctx, email, role=role)

@given(event_type_pattern)
def project_has_event_type(ctx: TestContext, project_name: str, event_type_code: str, event_type_name: str) -> None:
    project = _get_or_create_project(ctx, project_name)
    key = _event_type_key(project_name, event_type_code)
    if key not in _state(ctx)["event_types"]:
        _state(ctx)["event_types"][key] = ctx.factory.event_type(EventTypeRecord(project=project, code=event_type_code, name=event_type_name))

@given(metric_exists_pattern)
def metric_definition_exists(ctx: TestContext, project_name: str, event_type_code: str, metric_code: str) -> None:
    event_type = _get_event_type(ctx, project_name, event_type_code)
    ctx.factory.metric_definition(MetricDefinitionRecord(event_type=event_type, code=metric_code, name=metric_code))

@when(metric_create_pattern)
def metric_definition_is_created(ctx: TestContext, project_name: str, event_type_code: str, metric_code: str, metric_name: str) -> None:
    event_type = _get_event_type(ctx, project_name, event_type_code)
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions",
        json={"code": metric_code, "name": metric_name, "description": f"Metric {metric_name}"},
        headers=ctx.request_headers or {},
    )

@when(metric_create_unknown_event_type_pattern)
def metric_definition_is_created_for_unknown_event_type(ctx: TestContext, event_type_id: int, metric_code: str, metric_name: str) -> None:
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type_id}/metric-definitions",
        json={"code": metric_code, "name": metric_name, "description": f"Metric {metric_name}"},
        headers=ctx.request_headers or {},
    )

@when(metric_list_pattern)
def metric_definitions_are_listed(ctx: TestContext, project_name: str, event_type_code: str) -> None:
    event_type = _get_event_type(ctx, project_name, event_type_code)
    ctx.last_response = ctx.client.get(
        f"/api/admin/event-types/{event_type.id}/metric-definitions",
        headers=ctx.request_headers or {},
    )

@then(metric_should_be_registered_pattern)
def metric_definition_should_be_registered(ctx: TestContext, project_name: str, event_type_code: str, metric_code: str) -> None:
    event_type = _get_event_type(ctx, project_name, event_type_code)
    assert ctx.probe.metric_definition.exists_by_event_type_and_code(event_type=event_type, code=metric_code)

@then(metric_should_not_be_registered_pattern)
def metric_definition_should_not_be_registered(ctx: TestContext, project_name: str, event_type_code: str, metric_code: str) -> None:
    event_type = _get_event_type(ctx, project_name, event_type_code)
    assert not ctx.probe.metric_definition.exists_by_event_type_and_code(event_type=event_type, code=metric_code)

@then(metric_should_be_active_pattern)
def metric_definition_should_be_active(ctx: TestContext, project_name: str, event_type_code: str, metric_code: str) -> None:
    event_type = _get_event_type(ctx, project_name, event_type_code)
    assert ctx.probe.metric_definition.exists_active_by_event_type_and_code(event_type=event_type, code=metric_code)

@then(response_contains_metric_pattern)
def response_should_contain_metric_definition(ctx: TestContext, metric_code: str) -> None:
    assert ctx.last_response is not None
    payload = ctx.last_response.json()
    if isinstance(payload, list):
        assert any(item["code"] == metric_code for item in payload)
    else:
        assert payload["code"] == metric_code
