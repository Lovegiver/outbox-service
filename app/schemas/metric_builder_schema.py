from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

MetricBuilderIntent = Literal[
    "count_event",
    "count_by_label",
    "sum_value",
    "count_array_items",
    "measure_string_length",
    "count_boolean_true",
]


class MetricBuilderInputError(ValueError):
    """Raised for deterministic request composition errors after parsing."""


class _StrictBuilderModel(BaseModel):
    """Forbid silent acceptance of misspelled Builder properties."""

    model_config = {"extra": "forbid"}


class MetricBuilderSchemaField(_StrictBuilderModel):
    """
    JSON Schema field exposed to the Metrics Builder UI.

    The builder uses these descriptors to guide users toward meaningful
    Prometheus counter definitions without exposing raw JSON Schema internals.
    """

    path: str
    json_type: str
    required: bool
    nullable: bool
    analysis_status: Literal["SUPPORTED", "UNSAFE", "UNSUPPORTED"]
    analysis_reason: str
    label_allowed: bool
    label_rejection_reason: Optional[str] = None
    value_intents: list[str] = Field(default_factory=list)
    cardinality_risk: str
    warnings: list[str] = Field(default_factory=list)


class MetricBuilderSchemaFieldsResponse(_StrictBuilderModel):
    """
    Response containing the flattened fields available for one EventType schema.
    """

    event_type_id: int
    schema_definition_id: int
    fields: list[MetricBuilderSchemaField]


class MetricBuilderPreviewRequest(_StrictBuilderModel):
    """
    Request used to preview a business-oriented metric intent.

    The request is intentionally expressed as an intent plus selected paths.
    The service then generates the YAML projection used by the existing metrics
    engine.
    """

    schema_definition_id: Optional[int] = None
    metric_code: str = Field(min_length=1, max_length=150)
    intent: MetricBuilderIntent
    value_path: Optional[str] = None
    labels: dict[str, str] = Field(default_factory=dict)
    label_fields: list[str] = Field(default_factory=list)

    @field_validator("metric_code")
    @classmethod
    def reject_metric_code_controls(cls, value: str) -> str:
        """Reject control characters at the HTTP boundary."""
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError("metric_code must not contain control characters")
        return value

    @model_validator(mode="after")
    def reject_ambiguous_derived_labels(self) -> MetricBuilderPreviewRequest:
        """Reject label selections that would otherwise be silently overwritten."""
        names = list(self.labels)
        for field_path in self.label_fields:
            name = field_path.split(".")[-1].replace("[*]", "").lstrip("$")
            if name in names:
                raise ValueError(f"Duplicate derived label name '{name}'")
            names.append(name)
        if len(names) != len(set(names)):
            raise ValueError("Derived label names must be unique")
        return self

    def effective_labels(self, max_labels: Optional[int] = None) -> dict[str, str]:
        """
        Return explicit labels plus labels derived from selected schema fields.

        Returns:
            Mapping of Prometheus label names to JSON paths.
        """
        if max_labels is not None and (
            len(self.labels) > max_labels or len(self.label_fields) > max_labels
        ):
            raise MetricBuilderInputError(
                f"At most {max_labels} Builder labels are allowed"
            )

        effective = dict(self.labels)

        for field_path in self.label_fields:
            label_name = field_path.split(".")[-1].replace("[*]", "")
            label_name = label_name.lstrip("$")
            if label_name:
                effective.setdefault(label_name, field_path)

        if max_labels is not None and len(effective) > max_labels:
            raise MetricBuilderInputError(
                f"At most {max_labels} Builder labels are allowed"
            )

        return effective


class MetricBuilderPreviewResponse(_StrictBuilderModel):
    """
    Response returned after generating and validating a metric YAML draft.
    """

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    yaml_content: Optional[str] = None
    compiled_plan_json: Optional[dict] = None
    prometheus_metric_name: Optional[str] = None


class MetricBuilderCreateRequest(MetricBuilderPreviewRequest):
    """
    Request used to create a MetricDefinition and its first YAML version.
    """

    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=255)
    yaml_version_label: Optional[str] = Field(default=None, max_length=30)


class MetricBuilderCreateResponse(_StrictBuilderModel):
    """
    Response returned after creating a builder-generated metric definition.
    """

    metric_definition_id: int
    metric_definition_version_id: int
    metric_definition_version_schema_id: int
    schema_definition_id: int
    metric_code: str
    prometheus_metric_name: str
    yaml_content: str
    compiled_plan_json: dict
    created: bool
    warnings: list[str] = Field(default_factory=list)
