from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project


class ProjectRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        project: Project
    ) -> Project:

        self.db.add(project)
        self.db.commit()
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

        self.db.commit()
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
        self.db.commit()