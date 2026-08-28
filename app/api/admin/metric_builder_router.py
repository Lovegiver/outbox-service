from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_event_type_permission
from app.models import UserAccount
from app.schemas.metric_builder_schema import (
    MetricBuilderCreateRequest,
    MetricBuilderCreateResponse,
    MetricBuilderInputError,
    MetricBuilderPreviewRequest,
    MetricBuilderPreviewResponse,
    MetricBuilderSchemaField,
    MetricBuilderSchemaFieldsResponse,
)
from app.services.metric_builder_errors import (
    MetricBuilderAlreadyExistsError,
    MetricBuilderContractError,
    MetricBuilderCreationConflictError,
    MetricBuilderNameCollisionError,
    MetricBuilderNotFoundError,
    MetricBuilderScopeError,
    MetricBuilderUnsafeError,
    MetricBuilderUnsupportedError,
)

router = APIRouter(
    prefix="/api/admin/event-types/{event_type_id}/metric-builder",
    tags=["admin-metric-builder"],
)


@router.get(
    "/schema-fields",
    response_model=MetricBuilderSchemaFieldsResponse,
)
def list_metric_builder_schema_fields(
    event_type_id: int,
    schema_definition_id: Optional[int] = None,
    _: UserAccount = Depends(
        require_event_type_permission(ProjectPermission.METRICS_READ)
    ),
    db: Session = Depends(get_db),
) -> MetricBuilderSchemaFieldsResponse:
    """
    List JSON Schema fields available to the business metric builder.
    """
    service = ServiceFactory.create_metric_builder_service(db)

    try:
        schema_definition, fields = service.list_schema_fields(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        )

    except MetricBuilderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.public_message()) from exc
    except MetricBuilderScopeError as exc:
        raise HTTPException(status_code=403, detail=exc.public_message()) from exc
    except MetricBuilderUnsupportedError as exc:
        raise HTTPException(status_code=422, detail=exc.public_message()) from exc

    return MetricBuilderSchemaFieldsResponse(
        event_type_id=event_type_id,
        schema_definition_id=schema_definition.id,
        fields=[
            MetricBuilderSchemaField(
                path=field.path,
                json_type=field.json_type,
                required=field.required,
                nullable=field.nullable,
                analysis_status=field.analysis_status.value,
                analysis_reason=field.analysis_reason,
                label_allowed=field.label_allowed,
                label_rejection_reason=field.label_rejection_reason,
                value_intents=field.value_intents,
                cardinality_risk=field.cardinality_risk,
                warnings=field.warnings,
            )
            for field in fields
        ],
    )


@router.post(
    "/preview",
    response_model=MetricBuilderPreviewResponse,
)
def preview_metric_builder_definition(
    event_type_id: int,
    request: MetricBuilderPreviewRequest,
    _: UserAccount = Depends(
        require_event_type_permission(ProjectPermission.METRICS_WRITE)
    ),
    db: Session = Depends(get_db),
) -> MetricBuilderPreviewResponse:
    """
    Generate and validate YAML from a business metric intent.
    """
    service = ServiceFactory.create_metric_builder_service(db)

    try:
        preview = service.preview_metric(
            event_type_id=event_type_id,
            schema_definition_id=request.schema_definition_id,
            metric_code=request.metric_code,
            intent=request.intent,
            value_path=request.value_path,
            labels=request.effective_labels(service.limits.max_labels),
        )
    except MetricBuilderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.public_message()) from exc
    except MetricBuilderScopeError as exc:
        raise HTTPException(status_code=403, detail=exc.public_message()) from exc
    except MetricBuilderInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return MetricBuilderPreviewResponse(
        valid=preview.valid,
        errors=preview.errors,
        warnings=preview.warnings,
        yaml_content=preview.yaml_content,
        compiled_plan_json=preview.compiled_plan_json,
        prometheus_metric_name=preview.prometheus_metric_name,
    )


@router.post(
    "/create",
    response_model=MetricBuilderCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_metric_builder_definition(
    event_type_id: int,
    request: MetricBuilderCreateRequest,
    response: Response,
    _: UserAccount = Depends(
        require_event_type_permission(ProjectPermission.METRICS_WRITE)
    ),
    db: Session = Depends(get_db),
) -> MetricBuilderCreateResponse:
    """
    Create a MetricDefinition and first YAML version from a builder intent.
    """
    service = ServiceFactory.create_metric_builder_service(db)

    try:
        result = service.create_metric_from_builder(
            event_type_id=event_type_id,
            schema_definition_id=request.schema_definition_id,
            code=request.metric_code,
            name=request.name,
            description=request.description,
            intent=request.intent,
            value_path=request.value_path,
            labels=request.effective_labels(service.limits.max_labels),
            yaml_version_label=request.yaml_version_label,
        )

    except MetricBuilderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.public_message()) from exc
    except MetricBuilderScopeError as exc:
        raise HTTPException(status_code=403, detail=exc.public_message()) from exc
    except (
        MetricBuilderContractError,
        MetricBuilderUnsafeError,
        MetricBuilderUnsupportedError,
    ) as exc:
        raise HTTPException(status_code=422, detail=exc.public_message()) from exc
    except (
        MetricBuilderAlreadyExistsError,
        MetricBuilderCreationConflictError,
        MetricBuilderNameCollisionError,
    ) as exc:
        raise HTTPException(status_code=409, detail=exc.public_message()) from exc
    except MetricBuilderInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )
    return MetricBuilderCreateResponse(
        metric_definition_id=result.metric_definition.id,
        metric_definition_version_id=result.metric_definition_version.id,
        metric_definition_version_schema_id=result.compatibility.id,
        schema_definition_id=result.schema_definition.id,
        metric_code=result.metric_definition.code,
        prometheus_metric_name=result.prometheus_metric_name,
        yaml_content=result.yaml_content,
        compiled_plan_json=result.compiled_plan_json,
        created=result.created,
        warnings=result.warnings,
    )
