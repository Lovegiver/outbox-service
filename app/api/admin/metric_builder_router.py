from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.container.service_factory import ServiceFactory
from app.core.project_permission import ProjectPermission
from app.database import get_db
from app.dependencies import require_event_type_permission
from app.models import UserAccount
from app.schemas.metric_builder_schema import (
    MetricBuilderCreateRequest,
    MetricBuilderCreateResponse,
    MetricBuilderPreviewRequest,
    MetricBuilderPreviewResponse,
    MetricBuilderSchemaField,
    MetricBuilderSchemaFieldsResponse,
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

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MetricBuilderSchemaFieldsResponse(
        event_type_id=event_type_id,
        schema_definition_id=schema_definition.id,
        fields=[
            MetricBuilderSchemaField(
                path=field.path,
                json_type=field.json_type,
                required=field.required,
                label_allowed=field.label_allowed,
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

    preview = service.preview_metric(
        event_type_id=event_type_id,
        schema_definition_id=request.schema_definition_id,
        metric_code=request.metric_code,
        intent=request.intent,
        value_path=request.value_path,
        labels=request.effective_labels(),
    )

    return MetricBuilderPreviewResponse(
        valid=preview.valid,
        errors=preview.errors,
        warnings=preview.warnings,
        yaml_content=preview.yaml_content,
        compiled_plan_json=preview.compiled_plan_json,
    )


@router.post(
    "/create",
    response_model=MetricBuilderCreateResponse,
)
def create_metric_builder_definition(
    event_type_id: int,
    request: MetricBuilderCreateRequest,
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
            labels=request.effective_labels(),
            yaml_version_label=request.yaml_version_label,
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MetricBuilderCreateResponse(
        metric_definition_id=result.metric_definition.id,
        metric_definition_version_id=result.metric_definition_version.id,
        yaml_content=result.yaml_content,
        warnings=result.warnings,
    )
