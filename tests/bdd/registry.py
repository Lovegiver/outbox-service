from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tests.infrastructure.context import TestContext


UserRegistrationAssertion = Callable[[TestContext, str, str], None]
ProjectAssertion = Callable[..., None]
ProjectMemberAssertion = Callable[[TestContext, str, str, str], None]
ApiKeyAssertion = Callable[..., None]
EventAssertion = Callable[..., None]
EventTypeAssertion = Callable[[TestContext, str, str], None]
SchemaDefinitionAssertion = Callable[..., None]
RouteDefinitionAssertion = Callable[..., None]
EventDeliveryAssertion = Callable[..., None]
ResponseAssertion = Callable[..., None]


@dataclass(frozen=True)
class StepRegistry:
    user_registration_assertions: dict[str, UserRegistrationAssertion]
    project_assertions: dict[str, ProjectAssertion]
    project_member_assertions: dict[str, ProjectMemberAssertion]
    api_key_assertions: dict[str, ApiKeyAssertion]
    event_assertions: dict[str, EventAssertion]
    event_type_assertions: dict[str, EventTypeAssertion]
    schema_definition_assertions: dict[str, SchemaDefinitionAssertion]
    route_definition_assertions: dict[str, RouteDefinitionAssertion]
    event_delivery_assertions: dict[str, EventDeliveryAssertion]
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

    def api_key_assertion_for(self, state: str) -> ApiKeyAssertion:
        return self._resolve(self.api_key_assertions, "api key", state)

    def event_assertion_for(self, state: str) -> EventAssertion:
        return self._resolve(self.event_assertions, "event", state)

    def event_type_assertion_for(self, state: str) -> EventTypeAssertion:
        return self._resolve(self.event_type_assertions, "event type", state)

    def schema_definition_assertion_for(self, state: str) -> SchemaDefinitionAssertion:
        return self._resolve(
            self.schema_definition_assertions,
            "schema definition",
            state,
        )

    def route_definition_assertion_for(self, state: str) -> RouteDefinitionAssertion:
        return self._resolve(
            self.route_definition_assertions,
            "route definition",
            state,
        )

    def event_delivery_assertion_for(self, state: str) -> EventDeliveryAssertion:
        return self._resolve(
            self.event_delivery_assertions,
            "event delivery",
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
            "is absent": assert_project_member_is_absent,
        },
        api_key_assertions={
            "is active": assert_api_key_is_active,
            "is revoked": assert_api_key_is_revoked,
            "latest is active": assert_latest_api_key_is_active,
            "is absent": assert_api_key_is_absent,
        },
        event_assertions={
            "last ingested event exists": assert_last_ingested_event_exists,
        },
        event_type_assertions={
            "exists": assert_event_type_exists,
            "is absent": assert_event_type_is_absent,
        },
        schema_definition_assertions={
            "exists": assert_schema_definition_exists,
            "is absent": assert_schema_definition_is_absent,
            "is active": assert_schema_definition_is_active,
            "matches json schema": assert_schema_definition_matches_json_schema,
        },
        route_definition_assertions={
            "is active": assert_route_definition_is_active,
            "targets url": assert_route_definition_targets_url,
            "is absent": assert_route_definition_is_absent,
        },
        event_delivery_assertions={
            "exists for event and destination": assert_event_delivery_exists_for_event_and_destination,
            "exists for event destination and url": assert_event_delivery_exists_for_event_destination_and_url,
        },
        response_assertions={
            "has status": assert_response_status,
            "identifies user": assert_response_identifies_user,
            "contains error": assert_response_contains_error,
            "contains access token": assert_response_contains_access_token,
            "contains global role": assert_response_contains_global_role,
            "contains project": assert_response_contains_project,
            "contains project member": assert_response_contains_project_member,
            "contains event type": assert_response_contains_event_type,
            "identifies event type": assert_response_identifies_event_type,
            "contains schema version": assert_response_contains_schema_version,
            "is empty list": assert_response_is_empty_list,
            "contains route": assert_response_contains_route,
            "contains api key secret": assert_response_contains_api_key_secret,
            "does not expose api key secret": assert_response_does_not_expose_api_key_secret,
            "does not expose complete api key secrets": assert_response_does_not_expose_complete_api_key_secrets,
            "contains api key": assert_response_contains_api_key,
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



def assert_response_contains_project_member(
    ctx: TestContext,
    email: str,
    role: str,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()
    members = _extract_project_member_items(payload)

    assert any(
        str(member.get("email")) == email
        and str(member.get("role")) == role
        for member in members
    )



def assert_response_contains_api_key_secret(ctx: TestContext) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()

    assert "api_key" in payload
    assert str(payload["api_key"]).startswith("obx_ingest_")


def assert_response_does_not_expose_api_key_secret(
    ctx: TestContext,
    api_key_name: str,
) -> None:
    assert ctx.last_response is not None

    state = getattr(ctx, "api_key_state", {})
    secret = state.get("secrets_by_name", {}).get(api_key_name)

    assert secret is not None
    assert secret not in str(ctx.last_response.json())


def assert_response_does_not_expose_complete_api_key_secrets(
    ctx: TestContext,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()
    api_keys = _extract_api_key_items(payload)

    for api_key in api_keys:
        assert "api_key" not in api_key
        assert "key_hash" not in api_key


def assert_response_contains_api_key(
    ctx: TestContext,
    api_key_name: str,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()
    api_keys = _extract_api_key_items(payload)

    assert any(
        str(api_key.get("name")) == api_key_name
        for api_key in api_keys
    )


def _extract_api_key_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("items", "api_keys", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    raise AssertionError(f"Cannot extract API keys from response payload: {payload!r}")


def assert_response_contains_event_type(
    ctx: TestContext,
    event_type_code: str,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()
    event_types = _extract_event_type_items(payload)

    assert any(
        str(event_type.get("code")) == event_type_code
        for event_type in event_types
    )


def assert_response_identifies_event_type(
    ctx: TestContext,
    event_type_code: str,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()

    assert payload["code"] == event_type_code
    assert "id" in payload
    assert "project_id" in payload


def assert_response_contains_schema_version(
    ctx: TestContext,
    version: str,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()
    schemas = _extract_schema_definition_items(payload)

    assert any(
        str(schema.get("json_version_internal")) == version
        for schema in schemas
    )


def assert_response_is_empty_list(ctx: TestContext) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()

    assert isinstance(payload, list)
    assert payload == []


def assert_response_contains_route(
    ctx: TestContext,
    destination_name: str,
) -> None:
    assert ctx.last_response is not None

    payload = ctx.last_response.json()
    routes = _extract_route_definition_items(payload)

    assert any(
        str(route.get("destination_name")) == destination_name
        for route in routes
    )


def _extract_route_definition_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("items", "routes", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    raise AssertionError(f"Cannot extract RouteDefinitions from response payload: {payload!r}")


def _extract_schema_definition_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("items", "schemas", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    raise AssertionError(f"Cannot extract SchemaDefinitions from response payload: {payload!r}")


def _extract_event_type_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("items", "event_types", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    raise AssertionError(f"Cannot extract EventTypes from response payload: {payload!r}")


def _extract_project_member_items(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("items", "members", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    raise AssertionError(
        f"Cannot extract project members from response payload: {payload!r}"
    )


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



def assert_project_member_is_absent(
    ctx: TestContext,
    project_name: str,
    email: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    user = ctx.probe.user_account.get_by_email(email)

    assert not ctx.probe.project_member.exists_by_project_and_user(
        project=project,
        user=user,
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


def _event_type_for(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
):
    project = ctx.probe.project.get_by_name(project_name)
    return ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )


def assert_route_definition_is_active(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    destination_name: str,
) -> None:
    event_type = _event_type_for(ctx, project_name, event_type_code)

    assert ctx.probe.route_definition.exists_active_by_event_type_and_destination(
        event_type=event_type,
        destination_name=destination_name,
    )


def assert_route_definition_targets_url(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    destination_name: str,
    destination_url: str,
) -> None:
    event_type = _event_type_for(ctx, project_name, event_type_code)

    assert ctx.probe.route_definition.exists_by_event_type_destination_and_url(
        event_type=event_type,
        destination_name=destination_name,
        destination_url=destination_url,
    )


def assert_route_definition_is_absent(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    destination_name: str,
) -> None:
    event_type = _event_type_for(ctx, project_name, event_type_code)

    assert not ctx.probe.route_definition.exists_by_event_type_and_destination(
        event_type=event_type,
        destination_name=destination_name,
    )


def assert_event_delivery_exists_for_event_and_destination(
    ctx: TestContext,
    event,
    destination_name: str,
) -> None:
    assert ctx.probe.event_delivery.exists_by_event_and_destination(
        event=event,
        destination_name=destination_name,
    )


def assert_event_delivery_exists_for_event_destination_and_url(
    ctx: TestContext,
    event,
    destination_name: str,
    destination_url: str,
) -> None:
    assert ctx.probe.event_delivery.exists_by_event_destination_and_url(
        event=event,
        destination_name=destination_name,
        destination_url=destination_url,
    )


def assert_event_type_is_absent(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    assert not ctx.probe.event_type.exists_by_project_and_code(
        project=project,
        code=event_type_code,
    )


def assert_schema_definition_is_absent(
    ctx: TestContext,
    event_type_code: str,
    version: str,
) -> None:
    event_type = ctx.probe.event_type.get_by_code(event_type_code)

    assert not ctx.probe.schema_definition.exists_by_event_type_and_version(
        event_type=event_type,
        json_version_internal=version,
    )


def assert_schema_definition_is_active(
    ctx: TestContext,
    event_type_code: str,
    version: str,
) -> None:
    event_type = ctx.probe.event_type.get_by_code(event_type_code)

    assert ctx.probe.schema_definition.exists_active_by_event_type_and_version(
        event_type=event_type,
        json_version_internal=version,
    )


def assert_schema_definition_matches_json_schema(
    ctx: TestContext,
    event_type_code: str,
    version: str,
    expected_json_schema: dict,
) -> None:
    event_type = ctx.probe.event_type.get_by_code(event_type_code)

    actual = ctx.probe.schema_definition.json_schema_by_event_type_and_version(
        event_type=event_type,
        json_version_internal=version,
    )

    assert actual == expected_json_schema


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



def assert_api_key_is_active(
    ctx: TestContext,
    project_name: str,
    api_key_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    assert ctx.probe.api_key.exists_active_by_project_and_name(
        project=project,
        name=api_key_name,
    )


def assert_api_key_is_revoked(
    ctx: TestContext,
    project_name: str,
    api_key_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    assert ctx.probe.api_key.exists_revoked_by_project_and_name(
        project=project,
        name=api_key_name,
    )


def assert_latest_api_key_is_active(
    ctx: TestContext,
    project_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    state = getattr(ctx, "api_key_state", {})
    latest_id = state.get("latest_id")

    assert latest_id is not None
    assert ctx.probe.api_key.exists_active_by_project_and_id(
        project=project,
        api_key_id=latest_id,
    )


def assert_api_key_is_absent(
    ctx: TestContext,
    project_name: str,
    api_key_name: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)

    assert not ctx.probe.api_key.exists_by_project_and_name(
        project=project,
        name=api_key_name,
    )


def assert_last_ingested_event_exists(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = ctx.probe.project.get_by_name(project_name)
    event_type = ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )
    state = getattr(ctx, "api_key_state", {})
    event_uuid = state.get("last_ingested_event_uuid")

    assert event_uuid is not None
    assert ctx.probe.event.exists_by_uuid_project_and_event_type(
        event_uuid=event_uuid,
        project=project,
        event_type=event_type,
    )
