from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import uuid4

import jwt

from app.services.jwt_service import JwtService
from tests.domain.persisted_object import PersistedUserAccount


@dataclass(frozen=True)
class AuthenticatedUser:
    user: PersistedUserAccount
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
        }


class AuthTestHelper:
    def headers_for(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
        }

    def no_token(self) -> dict[str, str]:
        return {}

    def malformed(self) -> dict[str, str]:
        return self.headers_for("not-a-valid-jwt")

    def valid(
        self,
        user: PersistedUserAccount,
        role: str = "USER",
    ) -> AuthenticatedUser:
        return self._authenticated_user(
            user=user,
            role=role,
            expires_delta=timedelta(minutes=30),
            secret_key=JwtService.SECRET_KEY,
        )

    def expired(
        self,
        user: PersistedUserAccount,
        role: str = "USER",
    ) -> AuthenticatedUser:
        return self._authenticated_user(
            user=user,
            role=role,
            expires_delta=timedelta(minutes=-1),
            secret_key=JwtService.SECRET_KEY,
        )

    def invalid_signature(
        self,
        user: PersistedUserAccount,
        role: str = "USER",
    ) -> AuthenticatedUser:
        return self._authenticated_user(
            user=user,
            role=role,
            expires_delta=timedelta(minutes=30),
            secret_key="wrong-test-secret",
        )

    def with_payload(self, payload: dict) -> str:
        return jwt.encode(
            payload,
            JwtService.SECRET_KEY,
            algorithm=JwtService.ALGORITHM,
        )

    def as_admin(self, user: PersistedUserAccount) -> dict[str, str]:
        return self.valid(user=user, role="ADMIN").headers

    def as_user(self, user: PersistedUserAccount) -> dict[str, str]:
        return self.valid(user=user, role="USER").headers

    def token_for(
        self,
        user: PersistedUserAccount,
        role: str = "USER",
    ) -> str:
        return self.valid(user=user, role=role).token

    def authenticate(
        self,
        user: PersistedUserAccount,
        role: str = "USER",
    ) -> AuthenticatedUser:
        return self.valid(user=user, role=role)

    def _authenticated_user(
        self,
        user: PersistedUserAccount,
        role: str,
        expires_delta: Optional[timedelta],
        secret_key: str,
    ) -> AuthenticatedUser:
        payload = {
            "typ": "access",
            "sub": str(user.id),
            "email": user.email,
            "role": role,
            "iat": datetime.now(UTC),
            "jti": str(uuid4()),
        }

        if expires_delta is not None:
            payload["exp"] = datetime.now(UTC) + expires_delta

        token = jwt.encode(
            payload,
            secret_key,
            algorithm=JwtService.ALGORITHM,
        )

        return AuthenticatedUser(
            user=user,
            token=token,
        )
