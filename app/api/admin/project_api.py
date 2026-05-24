from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.database import get_db
from app.schemas.project_schema import (
    ProjectCreateRequest,
    ProjectResponse,
)

router = APIRouter(
    prefix="/admin/projects",
    tags=["admin-projects"],
)


@router.post("", response_model=ProjectResponse)
def create_project(
    request: ProjectCreateRequest,
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)

    try:
        return service.create_project(
            name=request.name,
            description=request.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)
    return service.list_projects()


@router.patch("/{project_id}/disable", response_model=ProjectResponse)
def disable_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_project_service(db)

    try:
        return service.disable_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc