from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_event_type_permission
from app.models import UserAccount
from app.schemas.metric_definition_schema import (
    MetricDefinitionCreate,
    MetricDefinitionRead,
    MetricDefinitionVersionCreate,
    MetricDefinitionVersionRead,
    MetricDefinitionVersionSchemaRead,
)


router = APIRouter(
    prefix="/api/admin/event-types/{event_type_id}/metric-definitions",
    tags=["admin-metric-definitions"],
)


@router.post("", response_model=MetricDefinitionRead)
def create_metric_definition(
    event_type_id: int,
    request: MetricDefinitionCreate,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.METRICS_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Create a metric definition attached to an EventType.
    """
    service = ServiceFactory.create_metric_definition_admin_service(db)

    return service.create_metric_definition(
        event_type_id=event_type_id,
        code=request.code,
        name=request.name,
        description=request.description,
    )


@router.post(
    "/{metric_definition_id}/versions",
    response_model=MetricDefinitionVersionRead,
)
def create_metric_definition_version(
    event_type_id: int,
    metric_definition_id: int,
    request: MetricDefinitionVersionCreate,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.METRICS_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Create a YAML version for a metric definition.
    """
    service = ServiceFactory.create_metric_definition_admin_service(db)

    return service.create_metric_definition_version(
        metric_definition_id=metric_definition_id,
        yaml_version_number=request.yaml_version_number,
        yaml_version_label=request.yaml_version_label,
        yaml_content=request.yaml_content,
    )


@router.post(
    "/versions/{metric_definition_version_id}/schemas/{schema_definition_id}",
    response_model=MetricDefinitionVersionSchemaRead,
)
def create_metric_definition_version_schema_compatibility(
    event_type_id: int,
    metric_definition_version_id: int,
    schema_definition_id: int,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.METRICS_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    """
    Validate and activate a YAML/schema compatibility.

    This endpoint validates the YAML against the selected JSON schema,
    persists the compatibility, rebuilds the ProcessingChain, and activates
    the runtime analytical processing chain.
    """
    service = ServiceFactory.create_metric_definition_version_schema_service(db)

    return service.create_compatibility(
        metric_definition_version_id=metric_definition_version_id,
        schema_definition_id=schema_definition_id,
    )

@router.post(
    "/schemas/{schema_definition_id}/processing-chain/rebuild",
)
def rebuild_processing_chain(
    event_type_id: int,
    schema_definition_id: int,
    db: Session = Depends(get_db),
) -> dict:
    service = ServiceFactory.create_processing_chain_activation_service(db)

    chain = service.rebuild_and_activate_chain(
        event_type_id=event_type_id,
        schema_definition_id=schema_definition_id,
    )

    db.commit()
    db.refresh(chain)

    return {
        "id": chain.id,
        "event_type_id": chain.event_type_id,
        "schema_definition_id": chain.schema_definition_id,
        "version_number": chain.version_number,
        "status": chain.status,
        "is_active": chain.is_active,
    }