from app.models.project import Project
from app.repositories.project_repository import ProjectRepository


class ProjectService:

    def __init__(
        self,
        project_repository: ProjectRepository
    ):
        self.project_repository = project_repository

    def create_project(
        self,
        name: str,
        description: str | None = None
    ) -> Project:

        existing = self.project_repository.find_by_name(name)

        if existing:
            raise ValueError(
                f"Project '{name}' already exists"
            )

        project = Project(
            name=name,
            description=description,
            enabled=True
        )

        return self.project_repository.create(project)

    def list_projects(
        self
    ) -> list[Project]:

        return self.project_repository.list_all()

    def disable_project(
        self,
        project_id: int
    ) -> Project:

        project = self.project_repository.find_by_id(
            project_id
        )

        if not project:
            raise ValueError(
                f"Project {project_id} not found"
            )

        return self.project_repository.disable(
            project
        )