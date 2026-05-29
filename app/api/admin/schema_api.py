from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_event_type_permission
from app.models import UserAccount
from app.schemas.schema_definition_schema import (
    SchemaDefinitionCreate, SchemaDefinitionRead,
)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/admin/event-types/{event_type_id}/schemas",
    tags=["admin-schemas"],
)


@router.post("", response_model=SchemaDefinitionRead)
def create_schema(
    event_type_id: int,
    request: SchemaDefinitionCreate,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.SCHEMA_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_schema_service(db)

    return service.create_schema(
        event_type_id=event_type_id,
        json_version_client=request.json_version_client,
        json_version_internal=request.json_version_internal,
        json_schema=request.json_schema,
    )


@router.get("", response_model=list[SchemaDefinitionRead])
def list_active_schemas(
    event_type_id: int,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.SCHEMA_READ
        )
    ),
    db: Session = Depends(get_db),
):
    service = ServiceFactory.create_schema_service(db)

    active_schema = service.get_active_schema(event_type_id)

    if active_schema is None:
        return []

    return [active_schema]