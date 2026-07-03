from __future__ import annotations

from typing import Any, Optional

from pytest_bdd import given, parsers, then, when

from tests.domain.record import EventDeliveryRecord
from tests.domain.record import EventRecord
from tests.domain.record import EventTypeRecord
from tests.domain.record import ProjectMemberRecord
from tests.domain.record import ProjectRecord
from tests.domain.record import SchemaDefinitionRecord
from tests.domain.record import UserAccountRecord
from tests.infrastructure.context import TestContext

project_member_pattern = parsers.parse('project "{project_name}" has user "{email}" with role "{role}"')
user_exists_pattern = parsers.parse('user "{email}" exists')
dead_letter_delivery_pattern = parsers.parse('project "{project_name}" has dead letter delivery "{destination_name}" with error "{last_error}" after {attempt_count:d} attempts')
failed_delivery_pattern = parsers.parse('project "{project_name}" has failed delivery "{destination_name}" with error "{last_error}" after {attempt_count:d} attempts')
list_dead_letters_pattern = parsers.parse('dead letters are listed for project "{project_name}"')
retry_dead_letter_pattern = parsers.parse('dead letter "{destination_name}" is retried for project "{project_name}"')
retry_dead_letter_id_pattern = parsers.parse('dead letter id {delivery_id:d} is retried for project "{project_name}"')
retry_all_dead_letters_pattern = parsers.parse('all dead letters are retried for project "{project_name}"')
response_contains_dead_letter_pattern = parsers.parse('the response should contain dead letter "{destination_name}"')
response_not_contains_dead_letter_pattern = parsers.parse('the response should not contain dead letter "{destination_name}"')
dead_letter_attempt_count_pattern = parsers.parse('the dead letter "{destination_name}" should expose attempt count {attempt_count:d}')
dead_letter_last_error_pattern = parsers.parse('the dead letter "{destination_name}" should expose last error "{last_error}"')
dead_letter_event_uuid_pattern = parsers.parse('the dead letter "{destination_name}" should expose an event UUID')
delivery_status_pattern = parsers.parse('delivery "{destination_name}" should have status "{status}"')
delivery_attempt_count_pattern = parsers.parse('delivery "{destination_name}" should have attempt count {attempt_count:d}')
retry_all_count_pattern = parsers.parse('the retry-all response should report {retried_count:d} retried dead letters')


def _state(ctx: TestContext) -> dict[str, Any]:
    state = getattr(ctx, "dead_letter_state", None)
    if state is None:
        state = {"projects": {}, "users": {}, "deliveries": {}}
        setattr(ctx, "dead_letter_state", state)
    return state


def _get_or_create_project(ctx: TestContext, project_name: str):
    state = _state(ctx)
    if project_name not in state["projects"]:
        state["projects"][project_name] = ctx.factory.project(ProjectRecord(name=project_name))
    return state["projects"][project_name]


def _get_or_create_user(ctx: TestContext, email: str):
    state = _state(ctx)
    if email not in state["users"]:
        state["users"][email] = ctx.factory.user_account(UserAccountRecord(email=email))
    return state["users"][email]


def _delivery(ctx: TestContext, destination_name: str):
    delivery = _state(ctx)["deliveries"].get(destination_name)
    if delivery is None:
        raise AssertionError(f"No delivery registered with destination {destination_name}.")
    return delivery


def _response_dead_letter(ctx: TestContext, destination_name: str) -> Optional[dict]:
    assert ctx.last_response is not None
    for item in ctx.last_response.json():
        if item["destination_name"] == destination_name:
            return item
    return None


def _create_delivery(ctx: TestContext, project_name: str, destination_name: str, status: str, last_error: Optional[str], attempt_count: int):
    project = _get_or_create_project(ctx, project_name)
    event_type = ctx.factory.event_type(
        EventTypeRecord(
            project=project,
            code=f"{project_name.lower()}.article.analyzed.{destination_name}",
            name=f"{project_name} Article analyzed",
        )
    )
    schema_definition = ctx.factory.schema_definition(
        SchemaDefinitionRecord(event_type=event_type, json_schema={"type": "object"})
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
            destination_url=f"https://{destination_name}.example.test/webhook",
            status=status,
            attempt_count=attempt_count,
            last_error=last_error,
        )
    )
    _state(ctx)["deliveries"][destination_name] = delivery
    return delivery


@given(project_member_pattern)
def project_has_user_with_role(ctx: TestContext, project_name: str, email: str, role: str) -> None:
    project = _get_or_create_project(ctx, project_name)
    user = _get_or_create_user(ctx, email)
    ctx.factory.project_member(ProjectMemberRecord(project=project, user=user, role=role))


@given(user_exists_pattern)
def user_exists(ctx: TestContext, email: str) -> None:
    _get_or_create_user(ctx, email)


@given(dead_letter_delivery_pattern)
def project_has_dead_letter_delivery(ctx: TestContext, project_name: str, destination_name: str, last_error: str, attempt_count: int) -> None:
    _create_delivery(ctx, project_name, destination_name, "DEAD_LETTER", last_error, attempt_count)


@given(failed_delivery_pattern)
def project_has_failed_delivery(ctx: TestContext, project_name: str, destination_name: str, last_error: str, attempt_count: int) -> None:
    _create_delivery(ctx, project_name, destination_name, "FAILED", last_error, attempt_count)


@when(list_dead_letters_pattern)
def dead_letters_are_listed(ctx: TestContext, project_name: str) -> None:
    project = _get_or_create_project(ctx, project_name)
    ctx.last_response = ctx.client.get(f"/api/admin/projects/{project.id}/dead-letters", headers=ctx.request_headers or {})


@when(retry_dead_letter_pattern)
def dead_letter_is_retried(ctx: TestContext, destination_name: str, project_name: str) -> None:
    project = _get_or_create_project(ctx, project_name)
    delivery = _delivery(ctx, destination_name)
    ctx.last_response = ctx.client.post(f"/api/admin/projects/{project.id}/dead-letters/{delivery.id}/retry", headers=ctx.request_headers or {})


@when(retry_dead_letter_id_pattern)
def dead_letter_id_is_retried(ctx: TestContext, delivery_id: int, project_name: str) -> None:
    project = _get_or_create_project(ctx, project_name)
    ctx.last_response = ctx.client.post(f"/api/admin/projects/{project.id}/dead-letters/{delivery_id}/retry", headers=ctx.request_headers or {})


@when(retry_all_dead_letters_pattern)
def all_dead_letters_are_retried(ctx: TestContext, project_name: str) -> None:
    project = _get_or_create_project(ctx, project_name)
    ctx.last_response = ctx.client.post(f"/api/admin/projects/{project.id}/dead-letters/retry-all", headers=ctx.request_headers or {})


@then(response_contains_dead_letter_pattern)
def response_should_contain_dead_letter(ctx: TestContext, destination_name: str) -> None:
    assert _response_dead_letter(ctx, destination_name) is not None


@then(response_not_contains_dead_letter_pattern)
def response_should_not_contain_dead_letter(ctx: TestContext, destination_name: str) -> None:
    assert _response_dead_letter(ctx, destination_name) is None


@then(dead_letter_attempt_count_pattern)
def dead_letter_should_expose_attempt_count(ctx: TestContext, destination_name: str, attempt_count: int) -> None:
    item = _response_dead_letter(ctx, destination_name)
    assert item is not None
    assert item["attempt_count"] == attempt_count


@then(dead_letter_last_error_pattern)
def dead_letter_should_expose_last_error(ctx: TestContext, destination_name: str, last_error: str) -> None:
    item = _response_dead_letter(ctx, destination_name)
    assert item is not None
    assert item["last_error"] == last_error


@then(dead_letter_event_uuid_pattern)
def dead_letter_should_expose_event_uuid(ctx: TestContext, destination_name: str) -> None:
    item = _response_dead_letter(ctx, destination_name)
    assert item is not None
    assert item["event_uuid"]


@then(delivery_status_pattern)
def delivery_should_have_status(ctx: TestContext, destination_name: str, status: str) -> None:
    delivery = _delivery(ctx, destination_name)
    assert ctx.probe.event_delivery.status_by_id(delivery.id) == status


@then(delivery_attempt_count_pattern)
def delivery_should_have_attempt_count(ctx: TestContext, destination_name: str, attempt_count: int) -> None:
    delivery = _delivery(ctx, destination_name)
    assert ctx.probe.event_delivery.attempt_count_by_id(delivery.id) == attempt_count


@then(parsers.parse('delivery "{destination_name}" should have no last error'))
def delivery_should_have_no_last_error(ctx: TestContext, destination_name: str) -> None:
    delivery = _delivery(ctx, destination_name)
    assert ctx.probe.event_delivery.last_error_by_id(delivery.id) is None


@then(retry_all_count_pattern)
def retry_all_response_should_report_count(ctx: TestContext, retried_count: int) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.json()["retried_count"] == retried_count
