from app.models.user_account import UserAccount
from sqlalchemy import select
from sqlalchemy.orm import Session


class UserRepository:

    def __init__(self, db: Session):
        self.db = db

    def find_by_id(
        self,
        user_id: int,
    ) -> UserAccount | None:

        statement = (
            select(UserAccount)
            .where(UserAccount.id == user_id)
        )

        result = self.db.execute(statement)

        return result.scalar_one_or_none()

    def find_by_email(
        self,
        email: str,
    ) -> UserAccount | None:

        statement = (
            select(UserAccount)
            .where(UserAccount.email == email)
        )

        result = self.db.execute(statement)

        return result.scalar_one_or_none()

    def create(
        self,
        user: UserAccount,
    ) -> UserAccount:

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return user