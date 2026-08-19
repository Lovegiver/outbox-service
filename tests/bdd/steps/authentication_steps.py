
from datetime import UTC, datetime, timedelta
from uuid import uuid4

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


@given(parsers.parse('the user has an authentication token signed with the wrong secret for "{email}"'))
def user_has_wrong_signature_token(ctx: TestContext, email: str) -> None:
    user = ctx.probe.user_account.get_by_email(email)
    ctx.request_headers = ctx.auth.invalid_signature(user).headers


@given(parsers.parse('the user has an authentication token without subject for "{email}"'))
def user_has_token_without_subject(ctx: TestContext, email: str) -> None:
    user = ctx.probe.user_account.get_by_email(email)
    payload = _access_token_payload(user.id)
    payload.pop("sub")
    ctx.request_headers = ctx.auth.headers_for(ctx.auth.with_payload(payload))


@given("the user has an authentication token for an unknown user")
def user_has_token_for_unknown_user(ctx: TestContext) -> None:
    ctx.request_headers = ctx.auth.headers_for(
        ctx.auth.with_payload(_access_token_payload(999999))
    )


@given(parsers.parse('the user has a "{token_type}" token for "{email}"'))
def user_has_unexpected_type_token(
    ctx: TestContext,
    email: str,
    token_type: str,
) -> None:
    user = ctx.probe.user_account.get_by_email(email)
    payload = _access_token_payload(user.id)
    payload["typ"] = token_type
    ctx.request_headers = ctx.auth.headers_for(ctx.auth.with_payload(payload))


def _access_token_payload(user_id: int) -> dict:
    now = datetime.now(UTC)
    return {
        "typ": "access",
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": str(uuid4()),
    }


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


@when("a user registers with an empty email")
def user_registers_with_empty_email(ctx: TestContext) -> None:
    ctx.last_response = ctx.client.post(
        "/auth/register",
        json={"email": "", "password": "ValidPassword123!"},
    )


@when("a user registers with an empty password")
def user_registers_with_empty_password(ctx: TestContext) -> None:
    ctx.last_response = ctx.client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": ""},
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
