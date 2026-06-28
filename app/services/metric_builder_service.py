from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

import yaml

from app.metrics_engine.metric_plan_compiler import compile_metric_yaml_to_json
from app.metrics_engine.metric_yaml_validator import (
    MetricYamlValidationError,
    validate_metric_yaml,
)
from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.schema_definition import SchemaDefinition
from app.repositories.schema_repository import SchemaRepository
from app.services.metric_definition_admin_service import MetricDefinitionAdminService


@dataclass(frozen=True)
class BuilderField:
    """
    Flattened JSON Schema field exposed to the Metrics Builder.
    """

    path: str
    json_type: str
    required: bool
    label_allowed: bool
    value_intents: list[str]
    cardinality_risk: str
    warnings: list[str]


@dataclass(frozen=True)
class BuilderPreview:
    """
    Result of a builder preview operation.
    """

    valid: bool
    errors: list[str]
    warnings: list[str]
    yaml_content: Optional[str]
    compiled_plan_json: Optional[dict]


@dataclass(frozen=True)
class BuilderCreateResult:
    """
    Result of a builder create operation.
    """

    metric_definition: MetricDefinition
    metric_definition_version: MetricDefinitionVersion
    yaml_content: str
    warnings: list[str]


@dataclass(frozen=True)
class _FieldScanContext:
    """
    Internal context used while flattening a JSON Schema.
    """

    path: str
    required: bool


class MetricBuilderService:
    """
    Business-oriented facade above the technical YAML Metrics Observatory.

    The builder allows the UI to work with metric intents such as counting array
    items or summing numeric values. It generates YAML only as an exchange format
    consumed by the existing validator, compiler, and processing chain.
    """

    INTENT_TO_TRANSFORM = {
        "count_event": "constant",
        "count_by_label": "constant",
        "sum_value": "identity",
        "count_array_items": "count",
        "measure_string_length": "length",
        "count_boolean_true": "to_number",
    }

    DANGEROUS_LABEL_PATTERN = re.compile(
        r"(^id$|_id$|uuid|email|phone|token|session|correlation|event_uuid)",
        re.IGNORECASE,
    )

    def __init__(
        self,
        schema_repository: SchemaRepository,
        metric_definition_admin_service: MetricDefinitionAdminService,
    ) -> None:
        """
        Initialize the service.

        Args:
            schema_repository: Repository used to load EventType JSON schemas.
            metric_definition_admin_service: Service used to persist definitions.
        """
        self.schema_repository = schema_repository
        self.metric_definition_admin_service = metric_definition_admin_service

    def list_schema_fields(
        self,
        event_type_id: int,
        schema_definition_id: Optional[int] = None,
    ) -> tuple[SchemaDefinition, list[BuilderField]]:
        """
        Return flattened schema fields available to build metrics.

        Args:
            event_type_id: EventType owning the JSON schema.
            schema_definition_id: Optional explicit schema identifier. If absent,
                the active EventType schema is used.

        Returns:
            The resolved SchemaDefinition and its flattened builder fields.

        Raises:
            ValueError: If the schema cannot be found or does not belong to the
                requested EventType.
        """
        schema_definition = self._resolve_schema_definition(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        )

        return (
            schema_definition,
            self._flatten_schema(schema_definition.json_schema),
        )

    def preview_metric(
        self,
        event_type_id: int,
        metric_code: str,
        intent: str,
        value_path: Optional[str],
        labels: dict[str, str],
        schema_definition_id: Optional[int] = None,
    ) -> BuilderPreview:
        """
        Generate, validate, and compile a metric YAML draft.

        Args:
            event_type_id: EventType owning the metric.
            metric_code: Prometheus-compatible metric code without OB1 prefix.
            intent: Business metric intent selected by the user.
            value_path: Optional JSON path used as the metric value source.
            labels: Mapping of Prometheus label names to JSON paths.
            schema_definition_id: Optional schema used for validation.

        Returns:
            BuilderPreview containing YAML, warnings, and compiled plan.
        """
        try:
            schema_definition = self._resolve_schema_definition(
                event_type_id=event_type_id,
                schema_definition_id=schema_definition_id,
            )

            metric_yaml = self._build_metric_yaml(
                metric_code=metric_code,
                intent=intent,
                value_path=value_path,
                labels=labels,
            )

            warnings = self._build_cardinality_warnings(labels)

            validated_metric_yaml = validate_metric_yaml(
                metric_yaml=metric_yaml,
                json_schema=schema_definition.json_schema,
            )

            compiled_plan_json = compile_metric_yaml_to_json(
                validated_metric_yaml,
            )

            return BuilderPreview(
                valid=True,
                errors=[],
                warnings=warnings,
                yaml_content=yaml.safe_dump(
                    metric_yaml,
                    sort_keys=False,
                    allow_unicode=True,
                ),
                compiled_plan_json=compiled_plan_json,
            )

        except (MetricYamlValidationError, ValueError, yaml.YAMLError) as exc:
            return BuilderPreview(
                valid=False,
                errors=[str(exc)],
                warnings=[],
                yaml_content=None,
                compiled_plan_json=None,
            )

    def create_metric_from_builder(
        self,
        event_type_id: int,
        code: str,
        name: str,
        description: Optional[str],
        intent: str,
        value_path: Optional[str],
        labels: dict[str, str],
        schema_definition_id: Optional[int] = None,
        yaml_version_label: Optional[str] = None,
    ) -> BuilderCreateResult:
        """
        Create a MetricDefinition and first YAML version from a builder intent.

        Args:
            event_type_id: EventType owning the metric.
            code: Stable metric definition code.
            name: Human-readable name.
            description: Optional human-readable description.
            intent: Business metric intent selected by the user.
            value_path: Optional JSON path used as the metric value source.
            labels: Mapping of Prometheus label names to JSON paths.
            schema_definition_id: Optional schema used for validation.
            yaml_version_label: Optional label for the generated YAML version.

        Returns:
            Created definition, version, YAML content, and warnings.

        Raises:
            ValueError: If the generated metric is not valid.
        """
        preview = self.preview_metric(
            event_type_id=event_type_id,
            metric_code=code,
            intent=intent,
            value_path=value_path,
            labels=labels,
            schema_definition_id=schema_definition_id,
        )

        if not preview.valid or preview.yaml_content is None:
            raise ValueError("Metric builder preview is invalid: " + "; ".join(preview.errors))

        metric_definition = self.metric_definition_admin_service.create_metric_definition(
            event_type_id=event_type_id,
            code=code,
            name=name,
            description=description,
        )

        metric_definition_version = (
            self.metric_definition_admin_service.create_metric_definition_version(
                metric_definition_id=metric_definition.id,
                yaml_version_number=1,
                yaml_version_label=yaml_version_label,
                yaml_content=preview.yaml_content,
            )
        )

        return BuilderCreateResult(
            metric_definition=metric_definition,
            metric_definition_version=metric_definition_version,
            yaml_content=preview.yaml_content,
            warnings=preview.warnings,
        )

    def _resolve_schema_definition(
        self,
        event_type_id: int,
        schema_definition_id: Optional[int],
    ) -> SchemaDefinition:
        """
        Resolve and validate the schema used by builder operations.
        """
        if schema_definition_id is None:
            schema_definition = self.schema_repository.find_active_by_event_type(
                event_type_id,
            )
        else:
            schema_definition = self.schema_repository.find_by_id(
                schema_definition_id,
            )

        if schema_definition is None:
            raise ValueError("SchemaDefinition not found")

        if schema_definition.event_type_id != event_type_id:
            raise ValueError(
                f"SchemaDefinition id={schema_definition.id} does not belong "
                f"to EventType id={event_type_id}"
            )

        return schema_definition

    def _build_metric_yaml(
        self,
        metric_code: str,
        intent: str,
        value_path: Optional[str],
        labels: dict[str, str],
    ) -> dict[str, Any]:
        """
        Convert a business metric intent into the current YAML DSL structure.
        """
        transform = self.INTENT_TO_TRANSFORM.get(intent)

        if transform is None:
            raise ValueError(
                f"Unsupported metric intent '{intent}'. Supported intents: "
                f"{sorted(self.INTENT_TO_TRANSFORM)}"
            )

        observation: dict[str, Any] = {
            "code": metric_code,
            "transform": transform,
            "labels": labels,
        }

        if transform == "constant":
            if value_path is not None:
                raise ValueError(
                    f"Metric intent '{intent}' uses an implicit counter value; "
                    "do not provide value_path."
                )

        else:
            if value_path is None:
                raise ValueError(
                    f"Metric intent '{intent}' requires value_path."
                )
            observation["value_path"] = value_path

        return {
            "version": "1.0",
            "observations": [observation],
        }

    def _flatten_schema(self, schema: dict[str, Any]) -> list[BuilderField]:
        """
        Flatten a JSON Schema into selectable field descriptors.
        """
        fields: list[BuilderField] = []
        self._walk_schema_node(
            schema=schema,
            context=_FieldScanContext(path="$", required=True),
            fields=fields,
        )
        return fields

    def _walk_schema_node(
        self,
        schema: dict[str, Any],
        context: _FieldScanContext,
        fields: list[BuilderField],
    ) -> None:
        """
        Recursively scan a JSON Schema node.
        """
        json_type = self._normalize_json_type(schema.get("type"))

        if json_type == "object":
            required_properties = set(schema.get("required", []))
            properties = schema.get("properties", {})

            if not isinstance(properties, dict):
                return

            for property_name, child_schema in properties.items():
                if not isinstance(child_schema, dict):
                    continue

                child_path = f"{context.path}.{property_name}"
                child_required = context.required and property_name in required_properties
                self._walk_schema_node(
                    schema=child_schema,
                    context=_FieldScanContext(
                        path=child_path,
                        required=child_required,
                    ),
                    fields=fields,
                )
            return

        fields.append(
            self._build_field(
                path=context.path,
                json_type=json_type,
                required=context.required,
            )
        )

        if json_type == "array":
            items_schema = schema.get("items")
            if isinstance(items_schema, dict):
                self._walk_schema_node(
                    schema=items_schema,
                    context=_FieldScanContext(
                        path=f"{context.path}[*]",
                        required=context.required,
                    ),
                    fields=fields,
                )

    def _build_field(
        self,
        path: str,
        json_type: str,
        required: bool,
    ) -> BuilderField:
        """
        Build one field descriptor with allowed intents and warnings.
        """
        warnings = self._build_field_warnings(path=path, json_type=json_type)

        return BuilderField(
            path=path,
            json_type=json_type,
            required=required,
            label_allowed=json_type in {"string", "integer", "boolean"},
            value_intents=self._value_intents_for_type(json_type),
            cardinality_risk=self._cardinality_risk(path=path, json_type=json_type),
            warnings=warnings,
        )

    def _value_intents_for_type(self, json_type: str) -> list[str]:
        """
        Return metric intents supported by a JSON field type.
        """
        if json_type in {"number", "integer"}:
            return ["sum_value"]

        if json_type == "array":
            return ["count_array_items"]

        if json_type == "string":
            return ["measure_string_length"]

        if json_type == "boolean":
            return ["count_boolean_true"]

        return []

    def _build_field_warnings(self, path: str, json_type: str) -> list[str]:
        """
        Build user-facing warnings for one field.
        """
        warnings: list[str] = []
        field_name = path.split(".")[-1].replace("[*]", "")

        if self.DANGEROUS_LABEL_PATTERN.search(field_name):
            warnings.append(
                "Field name looks like a unique identifier; avoid using it as a Prometheus label."
            )

        if json_type == "number":
            warnings.append(
                "Numeric fields are usually unsafe as labels because they can create many series."
            )

        return warnings

    def _build_cardinality_warnings(self, labels: dict[str, str]) -> list[str]:
        """
        Build warnings for selected labels before metric creation.
        """
        warnings: list[str] = []

        for label_name, label_path in labels.items():
            path_tail = label_path.split(".")[-1].replace("[*]", "")

            if self.DANGEROUS_LABEL_PATTERN.search(label_name):
                warnings.append(
                    f"Label '{label_name}' looks like a unique identifier and may explode cardinality."
                )

            if self.DANGEROUS_LABEL_PATTERN.search(path_tail):
                warnings.append(
                    f"Label '{label_name}' uses path '{label_path}', which looks like a unique identifier."
                )

        return warnings

    def _cardinality_risk(self, path: str, json_type: str) -> str:
        """
        Estimate static cardinality risk from path naming and JSON type.
        """
        field_name = path.split(".")[-1].replace("[*]", "")

        if self.DANGEROUS_LABEL_PATTERN.search(field_name):
            return "high"

        if json_type in {"string", "number"}:
            return "medium"

        return "low"

    def _normalize_json_type(self, raw_type: Any) -> str:
        """
        Normalize JSON Schema type declarations to one simple type string.
        """
        if isinstance(raw_type, list):
            for item in raw_type:
                if isinstance(item, str) and item != "null":
                    return item
            return "unknown"

        if isinstance(raw_type, str):
            return raw_type

        return "unknown"
