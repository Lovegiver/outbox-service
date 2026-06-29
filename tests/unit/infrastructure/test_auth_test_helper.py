from app.services.jwt_service import JwtService
from tests.domain.record import UserAccountRecord


def test_auth_helper_creates_valid_bearer_token(
    factory,
    auth,
) -> None:
    user = factory.user_account(
        UserAccountRecord(
            email="test@example.test",
        )
    )

    authenticated_user = auth.authenticate(user)

    payload = JwtService.decode_token(
        authenticated_user.token
    )

    assert payload["sub"] == str(user.id)
    assert payload["email"] == user.email
    assert authenticated_user.headers == {
        "Authorization": f"Bearer {authenticated_user.token}",
    }