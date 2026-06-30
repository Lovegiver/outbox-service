from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.rstrip() + "\n", encoding="utf-8")


write(
    "tests/bdd/features/authentication.feature",
    """
Feature: Authentication

  Authentication allows users to register and authenticate themselves.

  Scenario: Register a new user
    Given no user is registered with email "alice@example.com"
    When a user registers with email "alice@example.com" and password "ValidPassword123!"
    Then the response should have status 200
    And a user should be registered with email "alice@example.com"
    And the response should identify user "alice@example.com"

  Scenario: Reject registration with an already used email
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    When a user registers with email "alice@example.com" and password "AnotherPassword123!"
    Then the response should have status 400
    And the response error should contain "already exists"

  Scenario: Login with valid credentials
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    When the user logs in with email "alice@example.com" and password "ValidPassword123!"
    Then the response should have status 200
    And the response should contain an access token

  Scenario: Reject login with an invalid password
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    When the user logs in with email "alice@example.com" and password "WrongPassword123!"
    Then the response should have status 401
    And the response error should contain "Invalid credentials"

  Scenario: Reject login for an unknown user
    Given no user is registered with email "unknown@example.com"
    When the user logs in with email "unknown@example.com" and password "ValidPassword123!"
    Then the response should have status 401
    And the response error should contain "Invalid credentials"

  Scenario: Retrieve the authenticated user identity
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user is authenticated as "alice@example.com"
    When the authenticated user identity is requested
    Then the response should have status 200
    And the response should identify user "alice@example.com"
    And the response should contain global role "USER"

  Scenario: Reject identity request without authentication
    When the authenticated user identity is requested without authentication
    Then the response should have status 403

  Scenario: Reject identity request with an invalid token
    Given the user has an invalid authentication token
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "Invalid token"

  Scenario: Reject identity request with an expired token
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | active         |
    And the user has an expired authentication token for "alice@example.com"
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "Token expired"

  Scenario: Reject identity request for an inactive user
    Given the following users are registered:
      | email             | password          | global role | account status |
      | alice@example.com | ValidPassword123! | USER        | inactive       |
    And the user is authenticated as "alice@example.com"
    When the authenticated user identity is requested
    Then the response should have status 401
    And the response error should contain "User not found or inactive"
""",
)

write(
    "tests/bdd/test_authentication_bdd.py",
    """
from pytest_bdd import scenarios

from tests.bdd.steps import authentication_steps as _authentication_steps  # noqa: F401
from tests.bdd.steps import response_steps as _response_steps  # noqa: F401
from tests.bdd.steps import user_steps as _user_steps  # noqa: F401


scenarios("features/authentication.feature")
""",
)

write(
    "tests/bdd/steps/__init__.py",
    """
\"\"\"Reusable pytest-bdd step modules.\"\"\"
""",
)

write(
    "tests/bdd/steps/user_steps.py",
    """
from pytest_bdd import given, parsers, then

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


@given(parsers.parse('{presence} user is registered with email "{email}"'))
def user_registration_precondition(
    ctx: TestContext,
    step_registry: StepRegistry,
    presence: str,
    email: str,
) -> None:
    step_registry.user_registration_assertion_for("is registered")(
        ctx=ctx,
        presence=presence,
        email=email,
    )


@given("the following users are registered:")
def following_users_are_registered(
    ctx: TestContext,
    datatable: list[list[str]],
) -> None:
    headers = datatable[0]
    rows = datatable[1:]

    for row in rows:
        user_data = dict(zip(headers, row))

        ctx.seed.user_registered(
            email=user_data["email"],
            password=user_data["password"],
            global_role=user_data["global role"],
            account_status=user_data["account status"],
        )


@then(parsers.parse('{presence} user should be registered with email "{email}"'))
def user_registration_assertion(
    ctx: TestContext,
    step_registry: StepRegistry,
    presence: str,
    email: str,
) -> None:
    step_registry.user_registration_assertion_for("is registered")(
        ctx=ctx,
        presence=presence,
        email=email,
    )
""",
)

write(
    "tests/bdd/steps/authentication_steps.py",
    """
from pytest_bdd import given, parsers, when

from tests.infrastructure.context import TestContext


@given(parsers.parse('the user is authenticated as "{email}"'))
def user_is_authenticated_as(
    ctx: TestContext,
    email: str,
) -> None:
    user = ctx.probe.user_account.get_by_email(email)
    ctx.request_headers = ctx.auth.as_user(user)


@given("the user has an invalid authentication token")
def user_has_invalid_authentication_token(
    ctx: TestContext,
) -> None:
    ctx.request_headers = ctx.auth.malformed()


@given(parsers.parse('the user has an expired authentication token for "{email}"'))
def user_has_expired_authentication_token(
    ctx: TestContext,
    email: str,
) -> None:
    user = ctx.probe.user_account.get_by_email(email)
    ctx.request_headers = ctx.auth.expired(user).headers


@when(parsers.parse('a user registers with email "{email}" and password "{password}"'))
def user_registers(
    ctx: TestContext,
    email: str,
    password: str,
) -> None:
    ctx.last_response = ctx.client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )


@when(parsers.parse('the user logs in with email "{email}" and password "{password}"'))
def user_logs_in(
    ctx: TestContext,
    email: str,
    password: str,
) -> None:
    ctx.last_response = ctx.client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )


@when("the authenticated user identity is requested")
def authenticated_user_identity_is_requested(
    ctx: TestContext,
) -> None:
    ctx.last_response = ctx.client.get(
        "/auth/me",
        headers=ctx.request_headers or {},
    )


@when("the authenticated user identity is requested without authentication")
def authenticated_user_identity_is_requested_without_authentication(
    ctx: TestContext,
) -> None:
    ctx.last_response = ctx.client.get(
        "/auth/me",
        headers={},
    )
""",
)

write(
    "tests/bdd/steps/response_steps.py",
    """
from pytest_bdd import parsers, then

from tests.bdd.registry import StepRegistry
from tests.infrastructure.context import TestContext


@then(parsers.parse("the response should have status {status_code:d}"))
def response_should_have_status(
    ctx: TestContext,
    step_registry: StepRegistry,
    status_code: int,
) -> None:
    step_registry.response_assertion_for("has status")(
        ctx=ctx,
        expected_status=status_code,
    )


@then(parsers.parse('the response should identify user "{email}"'))
def response_should_identify_user(
    ctx: TestContext,
    step_registry: StepRegistry,
    email: str,
) -> None:
    step_registry.response_assertion_for("identifies user")(
        ctx=ctx,
        email=email,
    )


@then(parsers.parse('the response error should contain "{message}"'))
def response_error_should_contain(
    ctx: TestContext,
    step_registry: StepRegistry,
    message: str,
) -> None:
    step_registry.response_assertion_for("contains error")(
        ctx=ctx,
        message=message,
    )


@then("the response should contain an access token")
def response_should_contain_access_token(
    ctx: TestContext,
    step_registry: StepRegistry,
) -> None:
    step_registry.response_assertion_for("contains access token")(
        ctx=ctx,
    )


@then(parsers.parse('the response should contain global role "{role}"'))
def response_should_contain_global_role(
    ctx: TestContext,
    step_registry: StepRegistry,
    role: str,
) -> None:
    step_registry.response_assertion_for("contains global role")(
        ctx=ctx,
        role=role,
    )
""",
)

write(
    "tests/bdd/registry.py",
    """
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tests.infrastructure.context import TestContext


UserRegistrationAssertion = Callable[[TestContext, str, str], None]
ProjectAssertion = Callable[[TestContext, str], None]
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
    assert message in str(detail)


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
""",
)

write(
    "tests/infrastructure/context.py",
    """
from __future__ import annotations

from dataclasses import dataclass
from httpx import Response
from typing import Optional

from fastapi.testclient import TestClient

from tests.infrastructure.assertions import TestAssertions
from tests.infrastructure.auth import AuthTestHelper
from tests.infrastructure.object_factory import ObjectFactory
from tests.infrastructure.probe import Probe
from tests.infrastructure.seed import Seed


@dataclass
class TestContext:
    __test__ = False

    client: TestClient
    factory: ObjectFactory
    probe: Probe
    auth: AuthTestHelper
    seed: Seed
    assertions: TestAssertions
    last_response: Optional[Response] = None
    request_headers: Optional[dict[str, str]] = None
""",
)

print("BDD authentication files written.")
