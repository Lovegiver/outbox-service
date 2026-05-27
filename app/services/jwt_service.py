from datetime import datetime, timedelta, UTC
import jwt

from app.models.user_account import UserAccount


class JwtService:

    SECRET_KEY = "CHANGE_ME"
    ALGORITHM = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    @classmethod
    def create_access_token(
        cls,
        user: UserAccount,
    ) -> str:

        expiration = datetime.now(
            UTC
        ) + timedelta(
            minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES
        )

        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "exp": expiration,
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

        return jwt.decode(
            token,
            cls.SECRET_KEY,
            algorithms=[cls.ALGORITHM],
        )