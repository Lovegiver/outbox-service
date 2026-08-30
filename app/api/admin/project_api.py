from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import (
    get_current_user,
    require_project_permission,
)
from app.models import UserAccount
from app.schemas.project_schema import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.services.project_errors import (
    ProjectConflictError,
    ProjectNotFoundError,
    ProjectServiceError,
    ProjectValidationError,
)

router = APIRouter(
    prefix="/api/admin/projects",
    tags=["admin-projects"],
)


def _raise_project_http_error(exc: ProjectServiceError) -> None:
    status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, ProjectNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ProjectConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, ProjectValidationError):
        status_code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=status_code, detail=exc.public_detail()) from exc


@router.post("", response_model=ProjectResponse)
def create_project(
    request: ProjectCreateRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)

    try:
        return service.create_project(
            owner_user_id=current_user.id,
            name=request.name,
            description=request.description,
        )
    except ProjectServiceError as exc:
        _raise_project_http_error(exc)


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)

    return service.list_projects(current_user=current_user)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    _: UserAccount = Depends(
        require_project_permission(ProjectPermission.PROJECT_READ)
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)
    try:
        return service.get_project(project_id)
    except ProjectServiceError as exc:
        _raise_project_http_error(exc)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    request: ProjectUpdateRequest,
    _: UserAccount = Depends(
        require_project_permission(ProjectPermission.PROJECT_WRITE)
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)
    try:
        return service.update_project(project_id, request.provided_values())
    except ProjectServiceError as exc:
        _raise_project_http_error(exc)


@router.patch("/{project_id}/disable", response_model=ProjectResponse)
def disable_project(
    project_id: int,
    _: UserAccount = Depends(
        require_project_permission(ProjectPermission.PROJECT_WRITE)
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)

    try:
        return service.disable_project(project_id)
    except ProjectServiceError as exc:
        _raise_project_http_error(exc)


@router.patch("/{project_id}/enable", response_model=ProjectResponse)
def enable_project(
    project_id: int,
    _: UserAccount = Depends(
        require_project_permission(ProjectPermission.PROJECT_WRITE)
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)
    try:
        return service.enable_project(project_id)
    except ProjectServiceError as exc:
        _raise_project_http_error(exc)
