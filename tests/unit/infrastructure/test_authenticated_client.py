from tests.domain.record import UserAccountRecord


def test_authenticated_client_can_call_protected_endpoint(ctx) -> None:
    user = ctx.factory.user_account(
        UserAccountRecord(
            email="auth-user@example.test",
        )
    )

    response = ctx.client.get(
        "/api/admin/projects",
        headers=ctx.auth.as_user(user),
    )

    ctx.assertions.http_ok(response)


def test_client_without_token_is_rejected(ctx) -> None:
    response = ctx.client.get(
        "/api/admin/projects",
        headers=ctx.auth.no_token(),
    )

    ctx.assertions.http_unauthorized(response)


def test_client_with_expired_token_is_rejected(ctx) -> None:
    user = ctx.factory.user_account(
        UserAccountRecord(
            email="expired-user@example.test",
        )
    )

    response = ctx.client.get(
        "/api/admin/projects",
        headers=ctx.auth.expired(user).headers,
    )

    ctx.assertions.http_unauthorized(response)


def test_client_with_invalid_signature_is_rejected(ctx) -> None:
    user = ctx.factory.user_account(
        UserAccountRecord(
            email="invalid-signature-user@example.test",
        )
    )

    response = ctx.client.get(
        "/api/admin/projects",
        headers=ctx.auth.invalid_signature(user).headers,
    )

    ctx.assertions.http_unauthorized(response)

