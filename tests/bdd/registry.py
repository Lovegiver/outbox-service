from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tests.infrastructure.context import TestContext


UserRegistrationAssertion = Callable[[TestContext, str, str], None]
ProjectAssertion = Callable[..., None]
ProjectMemberAssertion = Callable[[TestContext, str, str, str], None]
EventTypeAssertion = Callable[[TestContext, str, str], None]
SchemaDefinitionAssertion = Callable[[TestContext, str, str], None]
ResponseAssertion = Callable[..., None]


@dataclass(frozen=True)
class StepRegistry:
    user_registration_assertions: dict[str, UserRegistrationAssertion]
    project_assertions: dict[str, ProjectAssertion]
    project_member_assertions: dict[str, ProjectMemberAssertion]
    event_type_assertions: dict[str, EventTypeAssertion]
    schema_definition_assertions: dict[str, SchemaDefinitionAssertion]
    response_assertions: dict[str, ResponseAssertion]

    def user_registration_assertion_for(
        self,
        state: str,
    ) -> UserRegistrationAssertion:
        return self._resolve(
            self.user_registration_assertions,
            "user registration",
            state,
        )

    def project_assertion_for(self, state: str) -> ProjectAssertion:
        return self._resolve(self.project_assertions, "project", state)

    def project_member_assertion_for(self, state: str) -> ProjectMemberAssertion:
        return self._resolve(self.project_member_assertions, "project member", state)

    def event_type_assertion_for(self, state: str) -> EventTypeAssertion:
        return self._resolve(self.event_type_assertions, "event type", state)

    def schema_definition_assertion_for(self, state: str) -> SchemaDefinitionAssertion:
        return self._resolve(
            self.schema_definition_assertions,
            "schema definition",
            state,
        )

    def response_assertion_for(self, state: str) -> ResponseAssertion:
        return self._resolve(self.response_assertions, "response", state)

    @staticmethod
    def _resolve(registry: dict, object_type: str, state: str):
        try:
            return registry[state]
        except KeyError as exc:
            raise AssertionError(
                f'No "{state}" assertion registered for {object_type}.'
            ) from exc


def create_step_registry() -> StepRegistry:
    return StepRegistry(
        user_registration_assertions={
            "is registered": assert_user_registration_state,
        },
        project_assertions={
            "exists": assert_project_exists,
            "is registered": assert_project_registration_state,
            "has status": assert_project_status,
        },
        project_member_assertions={
            "has role": assert_project_member_has_role,
        },
        event_type_assertions={
            "exists": assert_event_type_exists,
        },
        schema_definition_assertions={
            "exists": assert_schema_definition_exists,
        },
        response_assertions={
            "has status": assert_response_status,
            "identifies user": assert_response_identifies_user,
            "contains error": assert_response_contains_error,
            "contains access token": assert_response_contains_access_token,
            "contains global role": assert_response_contains_global_role,
            "contains project": assert_response_contains_project,
        },
    )


def assert_user_registration_state(
    ctx: TestContext,
    presence: str,
    email: str,
) -> None:
    expected = presence == "a"
    actual = ctx.probe.user_account.exists_by_email(email)

    assert actual is expected


def assert_project_registration_state(
    ctx: TestContext,
    presence: str,
    project_name: str,
) -> None:
    expected = presence == "a"
    actual = ctx.probe.project.exists_by_name(project_name)

    assert actual is expected


def assert_project_status(
    ctx: TestContext,
    project_name: str,
    status: str,
) -> None:
    expected = status == "active"
    actual = ctx.probe.project.is_active_by_name(project_name)

    assert actual is expected


def assert_response_status(
    ctx: TestContext,
    expected_status: int,
) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.status_code == expected_status


def assert_response_identifies_user(
    ctx: TestContext,
    email: str,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()

    assert payload["email"] == email
    assert "id" in payload
    assert "role" in payload


def assert_response_contains_error(
    ctx: TestContext,
    message: str,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()
    detail = payload.get("detail")

    assert detail is not None
    assert message.lower() in str(detail).lower()


def assert_response_contains_access_token(
    ctx: TestContext,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()

    assert "access_token" in payload
    assert payload["access_token"]


def assert_response_contains_global_role(
    ctx: TestContext,
    role: str,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()

    assert payload["role"] == role


def assert_response_contains_project(
    ctx: TestContext,
    project_name: str,
    expected: bool,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()
    projects = _extract_project_items(payload)
    names = {str(project.get("name")) for project in projects}

    assert (project_name in names) is expected


def _extract_project_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("items", "projects", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    raise AssertionError(f"Cannot extract projects from response payload: {payload!r}")


def assert_project_exists(
    ctx: TestContext,
    project_name: str,
) -> None:
    assert ctx.probe.project.exists_by_name(project_name)


def assert_project_member_has_role(
    ctx: TestContext,
    project_name: str,
    email: str,
    role: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    user = ctx.probe.user_account.get_by_email(email)

    assert ctx.probe.project_member.exists_by_project_user_and_role(
        project=project,
        user=user,
        role=role,
    )


def assert_event_type_exists(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    assert ctx.probe.event_type.exists_by_project_and_code(
        project=project,
        code=event_type_code,
    )


def assert_schema_definition_exists(
    ctx: TestContext,
    event_type_code: str,
    version: str,
) -> None:
    event_type = ctx.probe.event_type.get_by_code(event_type_code)

    assert ctx.probe.schema_definition.exists_by_event_type_and_version(
        event_type=event_type,
        json_version_internal=version,
    )
