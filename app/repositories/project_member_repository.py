from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project_member import ProjectMember


class ProjectMemberRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

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

        result = self.db.execute(
            statement
        )

        return result.scalar_one_or_none()