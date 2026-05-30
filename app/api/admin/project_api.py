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
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/admin/projects",
    tags=["admin-projects"],
)


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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)

    return service.list_projects(
        current_user=current_user
    )


@router.patch("/{project_id}/disable", response_model=ProjectResponse)
def disable_project(
    project_id: int,
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.PROJECT_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)

    try:
        return service.disable_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc