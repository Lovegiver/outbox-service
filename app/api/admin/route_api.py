from app.container.service_factory import ServiceFactory
from app.database import get_db
from app.schemas.route_definition_schema import (
    RouteDefinitionCreateRequest,
    RouteDefinitionResponse,
)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/admin/projects/{project_id}/routes",
    tags=["admin-routes"],
)


@router.post("", response_model=RouteDefinitionResponse)
def create_route(
    project_id: int,
    request: RouteDefinitionCreateRequest,
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_route_service(db)

    return service.create_route(
        project_id=project_id,
        routing_key=request.routing_key,
        destination_name=request.destination_name,
        destination_url=request.destination_url,
    )


@router.get("", response_model=list[RouteDefinitionResponse])
def list_project_routes(
    project_id: int,
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_route_service(db)
    return service.get_project_routes(project_id)