from app.core.auth_enums import ProjectMemberRole
from app.models.project_member import ProjectMember
from app.models.user_account import UserAccount
from sqlalchemy import func, select
from sqlalchemy.orm import Session


class ProjectMemberRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def create(
        self,
        membership: ProjectMember,
    ) -> ProjectMember:

        self.db.add(membership)
        self.db.flush()
        self.db.refresh(membership)

        return membership

    def find_by_project_and_user(
        self,
        project_id: int,
        user_id: int,
    ) -> ProjectMember | None:

        statement = (
            select(ProjectMember)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )

        return self.db.execute(
            statement
        ).scalar_one_or_none()

    def list_by_project_id(
        self,
        project_id: int,
    ) -> list[ProjectMember]:

        statement = (
            select(ProjectMember)
            .join(UserAccount)
            .where(ProjectMember.project_id == project_id)
            .order_by(UserAccount.email)
        )

        return list(
            self.db.execute(statement).scalars().all()
        )

    def count_owners(
        self,
        project_id: int,
    ) -> int:

        statement = (
            select(func.count(ProjectMember.id))
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.role == ProjectMemberRole.OWNER,
            )
        )

        return int(
            self.db.execute(statement).scalar_one()
        )

    def update(
        self,
        membership: ProjectMember,
    ) -> ProjectMember:

        self.db.flush()
        self.db.refresh(membership)

        return membership

    def delete(
        self,
        membership: ProjectMember,
    ) -> None:

        self.db.delete(membership)
        self.db.flush()

