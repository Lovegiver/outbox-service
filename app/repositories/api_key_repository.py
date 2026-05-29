from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey


class ApiKeyRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def create(
        self,
        api_key: ApiKey,
    ) -> ApiKey:

        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)

        return api_key

    def find_active_by_prefix(
        self,
        key_prefix: str,
    ) -> ApiKey | None:

        statement = (
            select(ApiKey)
            .where(
                ApiKey.key_prefix == key_prefix,
                ApiKey.is_active.is_(True),
            )
        )

        result = self.db.execute(statement)

        return result.scalar_one_or_none()

    def list_by_project(
        self,
        project_id: int,
    ) -> list[ApiKey]:

        statement = (
            select(ApiKey)
            .where(ApiKey.project_id == project_id)
            .order_by(ApiKey.id)
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )


    def find_by_id_and_project(
        self,
        api_key_id: int,
        project_id: int,
    ) -> ApiKey | None:

        statement = (
            select(ApiKey)
            .where(
                ApiKey.id == api_key_id,
                ApiKey.project_id == project_id,
            )
        )

        return self.db.execute(statement).scalar_one_or_none()


    def update(
        self,
        api_key: ApiKey,
    ) -> ApiKey:

        self.db.flush()
        self.db.refresh(api_key)

        return api_key
