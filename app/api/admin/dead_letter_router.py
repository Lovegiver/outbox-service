from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_project_permission
from app.models import UserAccount
from app.schemas.dead_letter_schema import (
    DeadLetterRead,
    DeadLetterRetryAllResponse,
    DeadLetterRetryResponse,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/admin/projects/{project_id}/dead-letters",
    tags=["admin-dead-letters"],
)


@router.get(
    "",
    response_model=list[DeadLetterRead],
)
def list_dead_letters(
    project_id: int,
    _: UserAccount = Depends(
        require_project_permission(ProjectPermission.METRICS_READ)
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_dead_letter_service(db)

    return service.list_dead_letters_by_project(
        project_id=project_id,
    )


@router.post(
    "/{delivery_id}/retry",
    response_model=DeadLetterRetryResponse,
)
def retry_dead_letter(
    project_id: int,
    delivery_id: int,
    _: UserAccount = Depends(
        require_project_permission(ProjectPermission.ROUTE_WRITE)
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_dead_letter_service(db)

    try:
        return service.retry_dead_letter(
            project_id=project_id,
            delivery_id=delivery_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


@router.post(
    "/retry-all",
    response_model=DeadLetterRetryAllResponse,
)
def retry_all_dead_letters(
    project_id: int,
    _: UserAccount = Depends(
        require_project_permission(ProjectPermission.ROUTE_WRITE)
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_dead_letter_service(db)

    return service.retry_all_dead_letters_by_project(
        project_id=project_id,
    )