import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, UTC

from app.models.api_key import ApiKey
from app.repositories.api_key_repository import ApiKeyRepository


@dataclass(frozen=True)
class CreatedApiKey:
    api_key: ApiKey
    plain_key: str


class ApiKeyService:

    KEY_PREFIX = "obx_ingest"

    def __init__(
        self,
        api_key_repository: ApiKeyRepository,
    ):
        self.api_key_repository = api_key_repository


    @staticmethod
    def hash_key(
        plain_key: str,
    ) -> str:

        return hashlib.sha256(
            plain_key.encode("utf-8")
        ).hexdigest()


    def create_api_key(
        self,
        project_id: int,
        name: str,
    ) -> CreatedApiKey:

        random_part = secrets.token_urlsafe(32)

        plain_key = (
            f"{self.KEY_PREFIX}_{random_part}"
        )

        key_prefix = plain_key[:32]
        key_hash = self.hash_key(
            plain_key
        )

        api_key = ApiKey(
            project_id=project_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
        )

        created_api_key = self.api_key_repository.create(
            api_key
        )

        return CreatedApiKey(
            api_key=created_api_key,
            plain_key=plain_key,
        )

    def authenticate_api_key(
        self,
        plain_key: str,
    ) -> ApiKey | None:

        key_prefix = plain_key[:32]

        api_key = self.api_key_repository.find_active_by_prefix(
            key_prefix
        )

        if api_key is None:
            return None

        expected_hash = self.hash_key(
            plain_key
        )

        if not secrets.compare_digest(
            expected_hash,
            api_key.key_hash,
        ):
            return None

        api_key.last_used_at = datetime.now(
            UTC
        )

        return api_key

    def list_api_keys(
            self,
            project_id: int,
    ) -> list[ApiKey]:

        return self.api_key_repository.list_by_project(
            project_id
        )

    def revoke_api_key(
            self,
            project_id: int,
            api_key_id: int,
    ) -> ApiKey:

        api_key = (
            self.api_key_repository
            .find_by_id_and_project(
                api_key_id=api_key_id,
                project_id=project_id,
            )
        )

        if api_key is None:
            raise ValueError(
                f"API key {api_key_id} not found"
            )

        if not api_key.is_active:
            return api_key

        api_key.is_active = False
        api_key.revoked_at = datetime.now(UTC)

        revoked_key = self.api_key_repository.update(
            api_key
        )

        self.api_key_repository.db.commit()
        self.api_key_repository.db.refresh(revoked_key)

        return revoked_key

    def rotate_api_key(
            self,
            project_id: int,
            api_key_id: int,
    ) -> CreatedApiKey:

        old_api_key = (
            self.api_key_repository
            .find_by_id_and_project(
                api_key_id=api_key_id,
                project_id=project_id,
            )
        )

        if old_api_key is None:
            raise ValueError(
                f"API key {api_key_id} not found"
            )

        if not old_api_key.is_active:
            raise ValueError(
                f"API key {api_key_id} is not active"
            )

        new_key = self.create_api_key(
            project_id=project_id,
            name=f"{old_api_key.name}-rotated",
        )

        old_api_key.is_active = False
        old_api_key.revoked_at = datetime.now(UTC)

        self.api_key_repository.update(old_api_key)
        self.api_key_repository.db.commit()

        return new_key