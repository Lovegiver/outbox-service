from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_event_type_permission
from app.metrics_engine.metric_yaml_parser import MetricYamlParseError
from app.metrics_engine.metric_yaml_validator import (
    MetricYamlValidationError,
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
    ProcessingChainRead,
    SchemaMetricPropagationRequest,
    SchemaMetricPropagationResponse,
)
from app.services.metric_definition_admin_service import (
    MetricConfigurationNotFoundError,
    MetricConfigurationScopeError,
)
from app.services.processing_chain_errors import (
    ProcessingChainConflictError,
    ProcessingChainIncompleteError,
    ProcessingChainNotFoundError,
    ProcessingChainSelectionError,
)


router = APIRouter(
    prefix="/api/admin/event-types/{event_type_id}/metric-definitions",
    tags=["admin-metric-definitions"],
)


def _raise_resource_http_error(exc: ValueError) -> None:
    """Translate explicit resource errors into the public HTTP contract."""
    if isinstance(exc, MetricConfigurationNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=403, detail=str(exc)) from exc


def _raise_processing_http_error(exc: ValueError) -> None:
    """Translate narrow snapshot administration failures."""
    if isinstance(exc, ProcessingChainNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ProcessingChainConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=422, detail=str(exc)) from exc


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

    try:
        return service.create_metric_definition(
            event_type_id=event_type_id,
            code=request.code,
            name=request.name,
            description=request.description,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Metric definition already exists for this EventType",
        ) from exc

@router.get("", response_model=list[MetricDefinitionRead])
def list_metric_definitions(
    event_type_id: int,
    _: UserAccount = Depends(
        require_event_type_permission(
            ProjectPermission.METRICS_READ
        )
    ),
    db: Session = Depends(get_db),
):
    """
    List metric definitions attached to an EventType.
    """
    service = ServiceFactory.create_metric_definition_admin_service(db)

    return service.list_metric_definitions(
        event_type_id=event_type_id,
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

    try:
        return service.create_metric_definition_version(
            event_type_id=event_type_id,
            metric_definition_id=metric_definition_id,
            schema_definition_id=request.schema_definition_id,
            yaml_version_label=request.yaml_version_label,
            yaml_content=request.yaml_content,
        )
    except (
        MetricConfigurationNotFoundError,
        MetricConfigurationScopeError,
    ) as exc:
        _raise_resource_http_error(exc)
    except (MetricYamlParseError, MetricYamlValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Metric definition version conflict",
        ) from exc


@router.get(
    "/{metric_definition_id}/versions",
    response_model=list[MetricDefinitionVersionRead],
)
def list_metric_definition_versions(
    event_type_id: int,
    metric_definition_id: int,
    _: UserAccount = Depends(
        require_event_type_permission(ProjectPermission.METRICS_READ)
    ),
    db: Session = Depends(get_db),
):
    """List the immutable YAML version history for a MetricDefinition."""
    service = ServiceFactory.create_metric_definition_admin_service(db)

    try:
        return service.list_metric_definition_versions(
            event_type_id=event_type_id,
            metric_definition_id=metric_definition_id,
        )
    except (
        MetricConfigurationNotFoundError,
        MetricConfigurationScopeError,
    ) as exc:
        _raise_resource_http_error(exc)


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
    service = ServiceFactory.create_metric_definition_admin_service(db)

    try:
        service.preview_metric_yaml(
            event_type_id=event_type_id,
            schema_definition_id=request.schema_definition_id,
            yaml_content=request.yaml_content,
        )

        return MetricYamlValidationResponse(valid=True)

    except (
        MetricConfigurationNotFoundError,
        MetricConfigurationScopeError,
    ) as exc:
        _raise_resource_http_error(exc)
    except (MetricYamlParseError, MetricYamlValidationError) as exc:
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
    service = ServiceFactory.create_metric_definition_admin_service(db)

    try:
        preview = service.preview_metric_yaml(
            event_type_id=event_type_id,
            schema_definition_id=request.schema_definition_id,
            yaml_content=request.yaml_content,
        )

        return MetricYamlPreviewResponse(
            valid=True,
            compiled_plan_json=preview.compiled_plan_json,
        )

    except (
        MetricConfigurationNotFoundError,
        MetricConfigurationScopeError,
    ) as exc:
        _raise_resource_http_error(exc)
    except (MetricYamlParseError, MetricYamlValidationError) as exc:
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
    Validate and persist a YAML/schema compatibility.

    Snapshot rebuild and activation remain explicit separate operations.
    """
    service = ServiceFactory.create_metric_definition_version_schema_service(db)

    try:
        return service.create_compatibility(
            event_type_id=event_type_id,
            metric_definition_version_id=metric_definition_version_id,
            schema_definition_id=schema_definition_id,
        )
    except (
        MetricConfigurationNotFoundError,
        MetricConfigurationScopeError,
    ) as exc:
        _raise_resource_http_error(exc)
    except (MetricYamlParseError, MetricYamlValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post(
    "/schemas/{schema_definition_id}/processing-chain/rebuild",
    response_model=ProcessingChainRead,
)
def rebuild_processing_chain(
    event_type_id: int,
    schema_definition_id: int,
    _: UserAccount = Depends(
        require_event_type_permission(ProjectPermission.METRICS_WRITE)
    ),
    db: Session = Depends(get_db),
) -> ProcessingChainRead:
    """Build or reuse a complete snapshot without changing active state."""
    service = ServiceFactory.create_processing_chain_activation_service(db)
    try:
        return service.rebuild_chain(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        )
    except (
        MetricConfigurationNotFoundError,
        MetricConfigurationScopeError,
    ) as exc:
        _raise_resource_http_error(exc)
    except (
        ProcessingChainSelectionError,
        ProcessingChainIncompleteError,
        ProcessingChainConflictError,
    ) as exc:
        _raise_processing_http_error(exc)


@router.post(
    "/schemas/{target_schema_definition_id}/compatibilities/propagate",
    response_model=SchemaMetricPropagationResponse,
)
def propagate_metric_schema_compatibilities(
    event_type_id: int,
    target_schema_definition_id: int,
    request: SchemaMetricPropagationRequest,
    _: UserAccount = Depends(
        require_event_type_permission(ProjectPermission.METRICS_WRITE)
    ),
    db: Session = Depends(get_db),
) -> SchemaMetricPropagationResponse:
    """Revalidate the prior active snapshot against an explicit new schema."""
    service = ServiceFactory.create_schema_metric_propagation_service(db)
    try:
        return service.propagate(
            event_type_id=event_type_id,
            source_schema_definition_id=request.source_schema_definition_id,
            target_schema_definition_id=target_schema_definition_id,
        )
    except (
        MetricConfigurationNotFoundError,
        MetricConfigurationScopeError,
    ) as exc:
        _raise_resource_http_error(exc)
    except ProcessingChainSelectionError as exc:
        _raise_processing_http_error(exc)


@router.post(
    "/schemas/{schema_definition_id}/processing-chains/{processing_chain_id}/activate",
    response_model=ProcessingChainRead,
)
def activate_processing_chain(
    event_type_id: int,
    schema_definition_id: int,
    processing_chain_id: int,
    _: UserAccount = Depends(
        require_event_type_permission(ProjectPermission.METRICS_WRITE)
    ),
    db: Session = Depends(get_db),
) -> ProcessingChainRead:
    """Atomically activate a complete candidate built for this exact scope."""
    service = ServiceFactory.create_processing_chain_activation_service(db)
    try:
        return service.activate_chain(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
            processing_chain_id=processing_chain_id,
        )
    except (
        MetricConfigurationNotFoundError,
        MetricConfigurationScopeError,
    ) as exc:
        _raise_resource_http_error(exc)
    except (
        ProcessingChainNotFoundError,
        ProcessingChainIncompleteError,
        ProcessingChainConflictError,
    ) as exc:
        _raise_processing_http_error(exc)
