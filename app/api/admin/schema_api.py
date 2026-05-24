from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.database import get_db
from app.schemas.schema_definition_schema import (
    SchemaDefinitionCreateRequest,
    SchemaDefinitionResponse,
)

router = APIRouter(
    prefix="/admin/event-types/{event_type_id}/schemas",
    tags=["admin-schemas"],
)


@router.post("", response_model=SchemaDefinitionResponse)
def create_schema(
    event_type_id: int,
    request: SchemaDefinitionCreateRequest,
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_schema_service(db)

    return service.create_schema(
        event_type_id=event_type_id,
        name=request.name,
        version=request.version,
        json_schema=request.json_schema,
    )


@router.get("", response_model=list[SchemaDefinitionResponse])
def list_active_schemas(
    event_type_id: int,
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_schema_service(db)

    return service.get_active_schemas(event_type_id)