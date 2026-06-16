import yaml

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_event_type_permission
from app.metrics_engine.metric_plan_compiler import compile_metric_yaml_to_json
from app.metrics_engine.metric_yaml_validator import (
    MetricYamlValidationError,
    validate_metric_yaml,
)
from app.models import UserAccount
from app.schemas.metric_definition_schema import (
    MetricDefinitionCreate,
    MetricDefinitionRead,
    MetricDefinitionVersionCreate,
    MetricDefinitionVersionRead,
    MetricDefinitionVersionSchemaRead,
    MetricYamlValidationRequest,
    MetricYamlValidationResponse,
    MetricYamlPreviewResponse,
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
    "/yaml/validate",
    response_model=MetricYamlValidationResponse,
)
def validate_metric_yaml_content(
    event_type_id: int,
    request: MetricYamlValidationRequest,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.METRICS_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    schema_definition = ServiceFactory.create_schema_service(
        db
    ).schema_repository.find_by_id(
        request.schema_definition_id
    )

    if schema_definition is None:
        return MetricYamlValidationResponse(
            valid=False,
            errors=[
                f"SchemaDefinition id={request.schema_definition_id} not found"
            ],
        )

    try:
        metric_yaml = yaml.safe_load(request.yaml_content)

        validate_metric_yaml(
            metric_yaml=metric_yaml,
            json_schema=schema_definition.json_schema,
        )

        return MetricYamlValidationResponse(valid=True)

    except (yaml.YAMLError, MetricYamlValidationError, ValueError) as exc:
        return MetricYamlValidationResponse(
            valid=False,
            errors=[str(exc)],
        )


@router.post(
    "/yaml/preview",
    response_model=MetricYamlPreviewResponse,
)
def preview_metric_yaml_content(
    event_type_id: int,
    request: MetricYamlValidationRequest,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.METRICS_WRITE
        )
    ),
    db: Session = Depends(get_db),
):
    schema_definition = ServiceFactory.create_schema_service(
        db
    ).schema_repository.find_by_id(
        request.schema_definition_id
    )

    if schema_definition is None:
        return MetricYamlPreviewResponse(
            valid=False,
            errors=[
                f"SchemaDefinition id={request.schema_definition_id} not found"
            ],
        )

    try:
        metric_yaml = yaml.safe_load(request.yaml_content)

        validated_metric_yaml = validate_metric_yaml(
            metric_yaml=metric_yaml,
            json_schema=schema_definition.json_schema,
        )

        compiled_plan_json = compile_metric_yaml_to_json(
            validated_metric_yaml
        )

        return MetricYamlPreviewResponse(
            valid=True,
            compiled_plan_json=compiled_plan_json,
        )

    except (yaml.YAMLError, MetricYamlValidationError, ValueError) as exc:
        return MetricYamlPreviewResponse(
            valid=False,
            errors=[str(exc)],
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