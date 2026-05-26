from app.container.service_factory import ServiceFactory
from app.database import get_db
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
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_route_service(db)

    return service.create_route(
        event_type_id=event_type_id,
        routing_key=request.routing_key,
        destination_name=request.destination_name,
        destination_url=request.destination_url,
    )


@router.get("", response_model=list[RouteDefinitionResponse])
def list_event_type_routes(
    event_type_id: int,
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
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_route_service(db)

    return service.update_route(
        route_id=route_id,
        routing_key=request.routing_key,
        destination_name=request.destination_name,
        destination_url=request.destination_url,
    )