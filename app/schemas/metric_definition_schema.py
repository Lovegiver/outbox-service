from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MetricDefinitionCreate(BaseModel):
    """
    Request payload used to create a metric definition for an EventType.
    """

    code: str
    name: str
    description: Optional[str] = None


class MetricDefinitionRead(BaseModel):
    """
    API representation of a metric definition.
    """

    id: int
    event_type_id: int
    code: str
    name: str
    description: Optional[str]
    is_active: bool

    model_config = {
        "from_attributes": True,
    }


class MetricDefinitionVersionCreate(BaseModel):
    """
    Request payload used to create a YAML version for a metric definition.
    """

    schema_definition_id: int
    yaml_version_label: Optional[str] = None
    yaml_content: str


class MetricDefinitionVersionRead(BaseModel):
    """
    API representation of a metric definition YAML version.
    """

    id: int
    metric_definition_id: int
    yaml_version_number: int
    yaml_version_label: Optional[str]
    yaml_content: str
    is_active: bool

    model_config = {
        "from_attributes": True,
    }


class MetricDefinitionVersionSchemaRead(BaseModel):
    """
    API representation of a validated YAML/schema compatibility.
    """

    id: int
    metric_definition_version_id: int
    schema_definition_id: int

    model_config = {
        "from_attributes": True,
    }


class ProcessingChainRead(BaseModel):
    """Public administrative representation of an immutable snapshot."""

    id: int
    event_type_id: int
    schema_definition_id: int
    version_number: int
    status: str
    is_active: bool

    model_config = {"from_attributes": True}


class SchemaMetricPropagationRequest(BaseModel):
    """Explicitly identifies the prior schema whose active snapshot is reused."""

    source_schema_definition_id: int


class PropagatedMetricResultRead(BaseModel):
    """Compatibility result for one metric version during schema evolution."""

    metric_definition_id: int
    metric_definition_version_id: int
    compatible: bool
    reason: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SchemaMetricPropagationResponse(BaseModel):
    """Complete controlled-propagation report and candidate identity."""

    source_schema_definition_id: int
    target_schema_definition_id: int
    evaluated_count: int
    compatible_count: int
    incompatible_count: int
    results: list[PropagatedMetricResultRead]
    proposed_metric_definition_version_ids: list[int]
    candidate_processing_chain_id: Optional[int]
    activation_allowed: bool

    model_config = {"from_attributes": True}


class MetricYamlValidationRequest(BaseModel):
    """
    Request payload used to validate or preview a metric YAML against a JSON schema.
    """

    schema_definition_id: int
    yaml_content: str


class MetricYamlValidationResponse(BaseModel):
    """
    Response returned after validating a metric YAML.
    """

    valid: bool
    errors: list[str] = Field(default_factory=list)


class MetricYamlPreviewResponse(BaseModel):
    """
    Response returned after compiling a valid metric YAML into its runtime plan preview.
    """

    valid: bool
    errors: list[str] = Field(default_factory=list)
    compiled_plan_json: Optional[dict] = None
