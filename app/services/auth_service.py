from app.core.project_permission import ProjectPermission
from app.core.project_role_permissions import PROJECT_ROLE_PERMISSIONS
from app.models.user_account import UserAccount
from app.repositories.project_member_repository import (
    ProjectMemberRepository,
)
from app.repositories.user_repository import UserRepository
from app.services.password_service import PasswordService


class AuthService:

    def __init__(
            self,
            user_repository: UserRepository,
            project_member_repository: ProjectMemberRepository,
    ):
        self.user_repository = user_repository
        self.project_member_repository = (
            project_member_repository
        )

    def register(
        self,
        email: str,
        password: str,
    ) -> UserAccount:

        existing_user = self.user_repository.find_by_email(
            email
        )

        if existing_user:
            raise ValueError(
                "Email already exists"
            )

        user = UserAccount(
            email=email,
            password_hash=PasswordService.hash_password(
                password
            )
        )

        return self.user_repository.create(
            user
        )

    def authenticate(
        self,
        email: str,
        password: str,
    ) -> UserAccount | None:

        user = self.user_repository.find_by_email(
            email
        )

        if user is None:
            return None

        if not PasswordService.verify_password(
            password,
            user.password_hash,
        ):
            return None

        return user

    def find_user_by_id(
            self,
            user_id: int,
    ) -> UserAccount | None:

        return self.user_repository.find_by_id(
            user_id
        )

    def has_project_permission(
            self,
            user_id: int,
            project_id: int,
            permission: ProjectPermission,
    ) -> bool:

        membership = (
            self.project_member_repository
            .find_by_project_and_user(
                project_id=project_id,
                user_id=user_id,
            )
        )

        if membership is None:
            return False

        permissions = (
            PROJECT_ROLE_PERMISSIONS[
                membership.role
            ]
        )

        return permission in permissions