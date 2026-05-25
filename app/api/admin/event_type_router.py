from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.event_type_repository import EventTypeRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.event_type_schema import EventTypeCreate, EventTypeRead
from app.services.event_type_service import EventTypeService


router = APIRouter(
    prefix="/api/admin/event-types",
    tags=["admin-event-types"],
)


def get_event_type_service(
    db: Session = Depends(get_db),
) -> EventTypeService:
    return EventTypeService(
        event_type_repository=EventTypeRepository(db),
        project_repository=ProjectRepository(db),
    )


@router.post(
    "",
    response_model=EventTypeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event_type(
    payload: EventTypeCreate,
    service: EventTypeService = Depends(get_event_type_service),
):
    try:
        return service.create_event_type(payload)
    except ValueError as exc:
        message = str(exc)

        if "not found" in message:
            status_code = status.HTTP_404_NOT_FOUND
        elif "not active" in message:
            status_code = status.HTTP_409_CONFLICT
        elif "already exists" in message:
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc


@router.get(
    "/by-project/{project_id}",
    response_model=list[EventTypeRead],
)
def list_event_types_by_project(
    project_id: int,
    service: EventTypeService = Depends(get_event_type_service),
):
    try:
        return service.list_by_project(project_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{event_type_id}",
    response_model=EventTypeRead,
)
def get_event_type(
    event_type_id: int,
    service: EventTypeService = Depends(get_event_type_service),
):
    try:
        return service.get_event_type(event_type_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc