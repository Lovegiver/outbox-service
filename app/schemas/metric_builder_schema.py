from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MetricBuilderSchemaField(BaseModel):
    """
    JSON Schema field exposed to the Metrics Builder UI.

    The builder uses these descriptors to guide users toward meaningful
    Prometheus counter definitions without exposing raw JSON Schema internals.
    """

    path: str
    json_type: str
    required: bool
    label_allowed: bool
    value_intents: list[str] = Field(default_factory=list)
    cardinality_risk: str
    warnings: list[str] = Field(default_factory=list)


class MetricBuilderSchemaFieldsResponse(BaseModel):
    """
    Response containing the flattened fields available for one EventType schema.
    """

    event_type_id: int
    schema_definition_id: int
    fields: list[MetricBuilderSchemaField]


class MetricBuilderPreviewRequest(BaseModel):
    """
    Request used to preview a business-oriented metric intent.

    The request is intentionally expressed as an intent plus selected paths.
    The service then generates the YAML projection used by the existing metrics
    engine.
    """

    schema_definition_id: Optional[int] = None
    metric_code: str
    intent: str
    value_path: Optional[str] = None
    labels: dict[str, str] = Field(default_factory=dict)
    label_fields: list[str] = Field(default_factory=list)

    def effective_labels(self) -> dict[str, str]:
        """
        Return explicit labels plus labels derived from selected schema fields.

        Returns:
            Mapping of Prometheus label names to JSON paths.
        """
        effective = dict(self.labels)

        for field_path in self.label_fields:
            label_name = field_path.split(".")[-1].replace("[*]", "")
            label_name = label_name.lstrip("$")
            if label_name:
                effective.setdefault(label_name, field_path)

        return effective


class MetricBuilderPreviewResponse(BaseModel):
    """
    Response returned after generating and validating a metric YAML draft.
    """

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    yaml_content: Optional[str] = None
    compiled_plan_json: Optional[dict] = None


class MetricBuilderCreateRequest(MetricBuilderPreviewRequest):
    """
    Request used to create a MetricDefinition and its first YAML version.
    """

    name: str
    description: Optional[str] = None
    yaml_version_label: Optional[str] = None


class MetricBuilderCreateResponse(BaseModel):
    """
    Response returned after creating a builder-generated metric definition.
    """

    metric_definition_id: int
    metric_definition_version_id: int
    yaml_content: str
    warnings: list[str] = Field(default_factory=list)
