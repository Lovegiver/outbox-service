from typing import Optional


class ProjectServiceError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        field: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field

    def public_detail(self) -> dict[str, Optional[str]]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
        }


class ProjectNotFoundError(ProjectServiceError):
    def __init__(self, project_id: int) -> None:
        super().__init__(
            code="PROJECT_NOT_FOUND",
            message=f"Project {project_id} not found",
        )


class ProjectValidationError(ProjectServiceError):
    pass


class ProjectConflictError(ProjectServiceError):
    def __init__(self, name: str) -> None:
        super().__init__(
            code="PROJECT_NAME_CONFLICT",
            message=f"Project '{name}' already exists",
            field="name",
        )
