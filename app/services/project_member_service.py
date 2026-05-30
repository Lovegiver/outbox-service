from app.core.auth_enums import ProjectMemberRole
from app.models.project_member import ProjectMember
from app.repositories.project_member_repository import ProjectMemberRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository


class ProjectMemberService:

    def __init__(
        self,
        project_repository: ProjectRepository,
        project_member_repository: ProjectMemberRepository,
        user_repository: UserRepository,
    ):
        self.project_repository = project_repository
        self.project_member_repository = project_member_repository
        self.user_repository = user_repository

    def list_members(
        self,
        project_id: int,
    ) -> list[ProjectMember]:

        self._ensure_project_exists(project_id)

        return self.project_member_repository.list_by_project_id(
            project_id
        )

    def add_member(
        self,
        project_id: int,
        email: str,
        role: ProjectMemberRole,
    ) -> ProjectMember:

        self._ensure_project_exists(project_id)

        user = self.user_repository.find_by_email(email)

        if user is None:
            raise ValueError(
                f"User '{email}' not found"
            )

        existing = (
            self.project_member_repository
            .find_by_project_and_user(
                project_id=project_id,
                user_id=user.id,
            )
        )

        if existing is not None:
            raise ValueError(
                f"User '{email}' is already a project member"
            )

        membership = ProjectMember(
            project_id=project_id,
            user_id=user.id,
            role=role,
        )

        created_membership = (
            self.project_member_repository.create(
                membership
            )
        )

        self.project_member_repository.db.commit()
        self.project_member_repository.db.refresh(
            created_membership
        )

        return created_membership

    def update_member_role(
        self,
        project_id: int,
        user_id: int,
        role: ProjectMemberRole,
    ) -> ProjectMember:

        self._ensure_project_exists(project_id)

        membership = self._get_membership(
            project_id=project_id,
            user_id=user_id,
        )

        if (
            membership.role == ProjectMemberRole.OWNER
            and role != ProjectMemberRole.OWNER
        ):
            self._ensure_not_last_owner(project_id)

        membership.role = role

        updated_membership = (
            self.project_member_repository.update(
                membership
            )
        )

        self.project_member_repository.db.commit()
        self.project_member_repository.db.refresh(
            updated_membership
        )

        return updated_membership

    def remove_member(
        self,
        project_id: int,
        user_id: int,
    ) -> None:

        self._ensure_project_exists(project_id)

        membership = self._get_membership(
            project_id=project_id,
            user_id=user_id,
        )

        if membership.role == ProjectMemberRole.OWNER:
            self._ensure_not_last_owner(project_id)

        self.project_member_repository.delete(membership)
        self.project_member_repository.db.commit()

    def _ensure_project_exists(
        self,
        project_id: int,
    ) -> None:

        project = self.project_repository.find_by_id(project_id)

        if project is None:
            raise ValueError(
                f"Project {project_id} not found"
            )

    def _get_membership(
        self,
        project_id: int,
        user_id: int,
    ) -> ProjectMember:

        membership = (
            self.project_member_repository
            .find_by_project_and_user(
                project_id=project_id,
                user_id=user_id,
            )
        )

        if membership is None:
            raise ValueError(
                f"User {user_id} is not a member of project {project_id}"
            )

        return membership

    def _ensure_not_last_owner(
        self,
        project_id: int,
    ) -> None:

        owner_count = self.project_member_repository.count_owners(
            project_id
        )

        if owner_count <= 1:
            raise ValueError(
                "Cannot remove or downgrade the last project OWNER"
            )