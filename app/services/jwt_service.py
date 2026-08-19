from datetime import datetime, timedelta, UTC
from uuid import uuid4

import jwt
from app.models.user_account import UserAccount
from app.services.config_service import ConfigService


class JwtService:

    _config = ConfigService()
    SECRET_KEY = _config.get_jwt_secret_key()
    ALGORITHM = _config.get_jwt_algorithm()
    ACCESS_TOKEN_EXPIRE_MINUTES = (
        _config.get_access_token_expire_minutes()
    )

    @classmethod
    def create_access_token(
        cls,
        user: UserAccount,
    ) -> str:

        issued_at = datetime.now(UTC)
        expiration = issued_at + timedelta(
            minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES
        )

        payload = {
            "typ": "access",
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "iat": issued_at,
            "exp": expiration,
            "jti": str(uuid4()),
        }

        return jwt.encode(
            payload,
            cls.SECRET_KEY,
            algorithm=cls.ALGORITHM,
        )

    @classmethod
    def decode_token(
        cls,
        token: str,
    ) -> dict:

        payload = jwt.decode(
            token,
            cls.SECRET_KEY,
            algorithms=[cls.ALGORITHM],
            options={
                "require": ["typ", "sub", "iat", "exp", "jti"],
            },
        )

        if payload.get("typ") != "access":
            raise jwt.InvalidTokenError("Unexpected token type")

        return payload
