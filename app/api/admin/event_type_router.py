from app.core.auth_enums import UserRole
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_project_permission, get_current_user, get_auth_service
from app.models import UserAccount
from app.repositories.event_type_repository import EventTypeRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.event_type_schema import EventTypeCreate, EventTypeRead
from app.services.auth_service import AuthService
from app.services.event_type_service import EventTypeService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
    current_user: UserAccount = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    service: EventTypeService = Depends(get_event_type_service),
):
    if current_user.role != UserRole.ADMIN:
        has_permission = auth_service.has_project_permission(
            user_id=current_user.id,
            project_id=payload.project_id,
            permission=ProjectPermission.EVENT_TYPE_WRITE,
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient project permissions",
            )

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
    _: UserAccount = Depends(
        require_project_permission(
            ProjectPermission.EVENT_TYPE_READ
        )
    ),
    service: EventTypeService = Depends(
        get_event_type_service
    ),
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
    current_user: UserAccount = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    service: EventTypeService = Depends(get_event_type_service),
):
    try:
        event_type = service.get_event_type(event_type_id)

        if current_user.role != UserRole.ADMIN:
            has_permission = auth_service.has_project_permission(
                user_id=current_user.id,
                project_id=event_type.project_id,
                permission=ProjectPermission.EVENT_TYPE_READ,
            )

            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient project permissions",
                )

        return event_type

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

