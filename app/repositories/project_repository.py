from app.models.project import Project
from app.models.project_member import ProjectMember
from sqlalchemy import select
from sqlalchemy.orm import Session


class ProjectRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        project: Project
    ) -> Project:

        self.db.add(project)
        self.db.flush()
        self.db.refresh(project)

        return project

    def find_by_id(
        self,
        project_id: int
    ) -> Project | None:

        statement = (
            select(Project)
            .where(Project.id == project_id)
        )

        return self.db.execute(
            statement
        ).scalar_one_or_none()

    def find_by_name(
        self,
        name: str
    ) -> Project | None:

        statement = (
            select(Project)
            .where(Project.name == name)
        )

        return self.db.execute(
            statement
        ).scalar_one_or_none()

    def list_all(
        self
    ) -> list[Project]:

        statement = (
            select(Project)
            .order_by(Project.id)
        )

        return list(
            self.db.execute(
                statement
            ).scalars().all()
        )

    def update(
        self,
        project: Project
    ) -> Project:

        self.db.flush()
        self.db.refresh(project)

        return project

    def disable(
        self,
        project: Project
    ) -> Project:

        project.is_active = False

        return self.update(project)

    def delete(
        self,
        project: Project
    ) -> None:

        self.db.delete(project)
        self.db.flush()

    def list_by_user_id(
            self,
            user_id: int,
    ) -> list[Project]:

        statement = (
            select(Project)
            .join(
                ProjectMember,
                ProjectMember.project_id == Project.id,
            )
            .where(
                ProjectMember.user_id == user_id,
            )
            .order_by(Project.id)
        )

        return list(
            self.db.execute(
                statement
            ).scalars().all()
        )