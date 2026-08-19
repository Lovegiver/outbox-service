from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_event_type_permission
from app.models import UserAccount
from app.schemas.route_definition_schema import (
    RouteDefinitionCreateRequest,
    RouteDefinitionUpdateRequest,
    RouteDefinitionResponse,
)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/admin/event-types/{event_type_id}/routes",
    tags=["admin-routes"],
)


@router.post("", response_model=RouteDefinitionResponse)
def create_route(
    event_type_id: int,
    request: RouteDefinitionCreateRequest,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.ROUTE_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_route_service(db)

    return service.create_route(
        event_type_id=event_type_id,
        routing_key=request.routing_key,
        destination_name=request.destination_name,
        destination_url=request.destination_url,
        auth_type=request.auth_type,
        auth_config=request.auth_config,
        secret_ref=request.secret_ref,
    )


@router.get("", response_model=list[RouteDefinitionResponse])
def list_event_type_routes(
    event_type_id: int,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.ROUTE_READ
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_route_service(db)

    return service.get_event_type_routes(
        event_type_id
    )

@router.patch(
    "/{route_id}",
    response_model=RouteDefinitionResponse
)
def update_route(
    event_type_id: int,
    route_id: int,
    request: RouteDefinitionUpdateRequest,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.ROUTE_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_route_service(db)

    try:
        return service.update_route(
            route_id=route_id,
            routing_key=request.routing_key,
            destination_name=request.destination_name,
            destination_url=request.destination_url,
            auth_type=request.auth_type,
            auth_config=request.auth_config,
            secret_ref=request.secret_ref,
        )
    except ValueError as exc:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
