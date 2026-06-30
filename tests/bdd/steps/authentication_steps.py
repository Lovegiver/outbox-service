
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
