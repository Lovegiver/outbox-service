from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_enums import ProjectMemberRole, UserRole
from app.models import UserAccount
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.repositories.project_member_repository import ProjectMemberRepository
from app.repositories.project_repository import ProjectRepository
from app.services.project_errors import (
    ProjectConflictError,
    ProjectNotFoundError,
    ProjectValidationError,
)


class ProjectService:
    def __init__(
        self,
        db: Session,
        project_repository: ProjectRepository,
        project_member_repository: ProjectMemberRepository,
    ):
        self.db = db
        self.project_repository = project_repository
        self.project_member_repository = project_member_repository

    def create_project(
        self,
        owner_user_id: int,
        name: str,
        description: Optional[str] = None,
    ) -> Project:

        existing = self.project_repository.find_by_name(name)

        if existing:
            raise ProjectConflictError(name)

        project = Project(name=name, description=description, is_active=True)

        try:
            created_project = self.project_repository.create(project)
            membership = ProjectMember(
                project_id=created_project.id,
                user_id=owner_user_id,
                role=ProjectMemberRole.OWNER,
            )
            self.project_member_repository.create(membership)
            self.db.commit()
            self.db.refresh(created_project)
            return created_project
        except IntegrityError as exc:
            self.db.rollback()
            raise ProjectConflictError(name) from exc
        except Exception:
            self.db.rollback()
            raise

    def list_projects(
        self,
        current_user: UserAccount,
    ) -> list[Project]:

        if current_user.role == UserRole.ADMIN:
            return self.project_repository.list_all()

        return self.project_repository.list_by_user_id(current_user.id)

    def get_project(self, project_id: int) -> Project:
        project = self.project_repository.find_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    def update_project(
        self,
        project_id: int,
        updates: dict[str, Optional[str]],
    ) -> Project:
        if not updates:
            raise ProjectValidationError(
                code="PROJECT_UPDATE_EMPTY",
                message="At least one modifiable Project field is required",
            )

        try:
            project = self.project_repository.find_by_id_for_update(project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)

            if "name" in updates:
                name = updates["name"]
                if name is None:
                    raise ProjectValidationError(
                        code="PROJECT_NAME_INVALID",
                        message="Project name must not be null",
                        field="name",
                    )
                existing = self.project_repository.find_by_name(
                    name,
                    exclude_project_id=project_id,
                )
                if existing is not None:
                    raise ProjectConflictError(name)
                project.name = name

            if "description" in updates:
                project.description = updates["description"]

            updated = self.project_repository.update(project)
            self.db.commit()
            self.db.refresh(updated)
            return updated
        except IntegrityError as exc:
            self.db.rollback()
            name = updates.get("name") or "requested"
            raise ProjectConflictError(name) from exc
        except Exception:
            self.db.rollback()
            raise

    def disable_project(self, project_id: int) -> Project:

        try:
            project = self.project_repository.find_by_id_for_update(project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            if project.is_active:
                project = self.project_repository.disable(project)
            self.db.commit()
            self.db.refresh(project)
            return project
        except Exception:
            self.db.rollback()
            raise

    def enable_project(self, project_id: int) -> Project:
        try:
            project = self.project_repository.find_by_id_for_update(project_id)
            if project is None:
                raise ProjectNotFoundError(project_id)
            if not project.is_active:
                project = self.project_repository.enable(project)
            self.db.commit()
            self.db.refresh(project)
            return project
        except Exception:
            self.db.rollback()
            raise
