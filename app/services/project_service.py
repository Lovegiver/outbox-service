from app.core.auth_enums import ProjectMemberRole
from app.core.auth_enums import UserRole
from app.models import UserAccount
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.repositories.project_member_repository import ProjectMemberRepository
from app.repositories.project_repository import ProjectRepository


class ProjectService:

    def __init__(
            self,
            project_repository: ProjectRepository,
            project_member_repository: ProjectMemberRepository,
    ):
        self.project_repository = project_repository
        self.project_member_repository = project_member_repository

    def create_project(
            self,
            owner_user_id: int,
            name: str,
            description: str | None = None,
    ) -> Project:

        existing = self.project_repository.find_by_name(name)

        if existing:
            raise ValueError(
                f"Project '{name}' already exists"
            )

        project = Project(
            name=name,
            description=description,
            is_active=True
        )

        created_project = (
            self.project_repository.create(project)
        )

        membership = ProjectMember(
            project_id=created_project.id,
            user_id=owner_user_id,
            role=ProjectMemberRole.OWNER,
        )

        self.project_member_repository.create(membership)

        self.project_repository.db.commit()
        self.project_repository.db.refresh(created_project)

        return created_project

    def list_projects(
            self,
            current_user: UserAccount,
    ) -> list[Project]:

        if current_user.role == UserRole.ADMIN:
            return self.project_repository.list_all()

        return self.project_repository.list_by_user_id(
            current_user.id
        )

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

        disabled_project = self.project_repository.disable(
            project
        )

        self.project_repository.db.commit()
        self.project_repository.db.refresh(disabled_project)

        return disabled_project