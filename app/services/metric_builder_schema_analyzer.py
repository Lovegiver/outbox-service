"""Conservative JSON Schema analysis for the business Metrics Builder."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class SchemaAnalysisStatus(str, Enum):
    """Closed outcome of one Builder field analysis."""

    SUPPORTED = "SUPPORTED"
    UNSAFE = "UNSAFE"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class MetricBuilderAnalysisLimits:
    """Configurable bounds applied while inspecting untrusted schemas."""

    max_enum_values: int = 20
    max_labels: int = 5
    max_path_length: int = 512
    max_path_segments: int = 32
    max_schema_depth: int = 32
    max_schema_fields: int = 1000
    max_label_name_length: int = 128


@dataclass(frozen=True)
class AnalyzedBuilderField:
    """One deterministic field descriptor derived from an exact JSON Schema."""

    path: str
    json_type: str
    required: bool
    nullable: bool
    analysis_status: SchemaAnalysisStatus
    analysis_reason: str
    label_allowed: bool
    label_rejection_reason: Optional[str]
    value_intents: tuple[str, ...]
    cardinality_risk: str
    warnings: tuple[str, ...]


class MetricBuilderSchemaAnalysisError(ValueError):
    """Raised when schema complexity exceeds configured analysis bounds."""


_PROPERTY_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_HIGH_CARDINALITY_NAME = re.compile(
    r"(^id$|_id$|uuid|email|url|phone|token|session|correlation|timestamp)",
    re.IGNORECASE,
)
_COMPLEX_KEYWORDS = {
    "$ref",
    "$dynamicRef",
    "anyOf",
    "oneOf",
    "allOf",
    "not",
    "if",
    "then",
    "else",
}
_SCALAR_TYPES = {"string", "number", "integer", "boolean"}


class MetricBuilderSchemaAnalyzer:
    """Analyze only the bounded JSON Schema subset supported by BDD-016A."""

    def __init__(self, limits: MetricBuilderAnalysisLimits) -> None:
        """Initialize the analyzer with explicit operational limits."""
        self.limits = limits

    def analyze(self, schema: dict[str, Any]) -> list[AnalyzedBuilderField]:
        """Return stable field descriptors without mutating ``schema``."""
        if not isinstance(schema, dict):
            raise MetricBuilderSchemaAnalysisError("JSON Schema must be an object")

        fields: list[AnalyzedBuilderField] = []
        self._walk(
            schema=schema,
            path="$",
            ancestors_required=True,
            ancestors_nullable=False,
            depth=0,
            fields=fields,
        )
        return fields

    def _walk(
        self,
        *,
        schema: dict[str, Any],
        path: str,
        ancestors_required: bool,
        ancestors_nullable: bool,
        depth: int,
        fields: list[AnalyzedBuilderField],
    ) -> None:
        """Walk one node while enforcing deterministic resource bounds."""
        if depth > self.limits.max_schema_depth:
            raise MetricBuilderSchemaAnalysisError(
                f"JSON Schema exceeds maximum depth {self.limits.max_schema_depth}"
            )
        if any(keyword in schema for keyword in _COMPLEX_KEYWORDS):
            if path == "$":
                raise MetricBuilderSchemaAnalysisError(
                    "Complex JSON Schema root construction is unsupported"
                )
            self._append(
                fields,
                self._unsupported_field(
                    path, ancestors_required, "Complex JSON Schema construction"
                ),
            )
            return

        json_type, nullable, type_reason = self._effective_type(schema.get("type"))
        if type_reason is not None:
            if path != "$":
                self._append(
                    fields,
                    self._unsupported_field(path, ancestors_required, type_reason),
                )
            return

        if json_type == "object":
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            if (
                not isinstance(properties, dict)
                or not isinstance(required, list)
                or any(not isinstance(item, str) for item in required)
            ):
                if path != "$":
                    self._append(
                        fields,
                        self._unsupported_field(
                            path, ancestors_required, "Malformed object schema"
                        ),
                    )
                return
            required_names = set(required)
            for property_name in sorted(properties):
                child = properties[property_name]
                if not isinstance(child, dict):
                    child = {}
                child_path = f"{path}.{property_name}"
                child_required = ancestors_required and property_name in required_names
                if not _PROPERTY_NAME.fullmatch(property_name):
                    self._append(
                        fields,
                        self._unsupported_field(
                            child_path,
                            child_required,
                            "Property name is outside the supported path grammar",
                        ),
                    )
                    continue
                self._validate_path_bounds(child_path)
                self._walk(
                    schema=child,
                    path=child_path,
                    ancestors_required=child_required,
                    ancestors_nullable=ancestors_nullable or nullable,
                    depth=depth + 1,
                    fields=fields,
                )
            return

        if path == "$":
            raise MetricBuilderSchemaAnalysisError(
                "Builder JSON Schema root must be an object"
            )

        self._append(
            fields,
            self._build_field(
                schema=schema,
                path=path,
                json_type=json_type,
                required=ancestors_required,
                nullable=nullable,
                ancestor_nullable=ancestors_nullable,
            ),
        )

        if json_type == "array":
            items = schema.get("items")
            if isinstance(items, dict):
                item_path = f"{path}[*]"
                self._validate_path_bounds(item_path)
                self._walk(
                    schema=items,
                    path=item_path,
                    ancestors_required=ancestors_required,
                    ancestors_nullable=ancestors_nullable or nullable,
                    depth=depth + 1,
                    fields=fields,
                )

    def _append(
        self,
        fields: list[AnalyzedBuilderField],
        field: AnalyzedBuilderField,
    ) -> None:
        """Append a field while enforcing the configured field-count bound."""
        if len(fields) >= self.limits.max_schema_fields:
            raise MetricBuilderSchemaAnalysisError(
                f"JSON Schema exceeds maximum field count "
                f"{self.limits.max_schema_fields}"
            )
        fields.append(field)

    def _build_field(
        self,
        *,
        schema: dict[str, Any],
        path: str,
        json_type: str,
        required: bool,
        nullable: bool,
        ancestor_nullable: bool,
    ) -> AnalyzedBuilderField:
        """Build the compatibility and label decision for one understood field."""
        value_intents: tuple[str, ...]
        status = SchemaAnalysisStatus.SUPPORTED
        reason = "Field construction is supported"
        if json_type in {"number", "integer"}:
            bound_status, bound_reason = self._numeric_bound_status(schema)
            if bound_status == "safe":
                value_intents = ("sum_value",)
            elif bound_status == "unsupported":
                value_intents = ()
                status = SchemaAnalysisStatus.UNSUPPORTED
                reason = bound_reason
            else:
                value_intents = ()
                status = SchemaAnalysisStatus.UNSAFE
                reason = bound_reason
        elif json_type == "array":
            value_intents = ("count_array_items",)
        elif json_type == "string":
            value_intents = ("measure_string_length",)
        elif json_type == "boolean":
            value_intents = ("count_boolean_true",)
        else:
            value_intents = ()
            status = SchemaAnalysisStatus.UNSAFE
            reason = f"No Counter intent supports JSON type '{json_type}'"

        label_allowed, rejection, risk = self._label_decision(
            path=path,
            json_type=json_type,
            nullable=nullable or ancestor_nullable,
            schema=schema,
        )
        warnings: tuple[str, ...] = ()
        if not label_allowed and rejection is not None:
            warnings = (rejection,)

        return AnalyzedBuilderField(
            path=path,
            json_type=json_type,
            required=required,
            nullable=nullable or ancestor_nullable,
            analysis_status=status,
            analysis_reason=reason,
            label_allowed=label_allowed,
            label_rejection_reason=rejection,
            value_intents=value_intents,
            cardinality_risk=risk,
            warnings=warnings,
        )

    def _unsupported_field(
        self,
        path: str,
        required: bool,
        reason: str,
    ) -> AnalyzedBuilderField:
        """Return an explicit descriptor for a construction not analyzed."""
        return AnalyzedBuilderField(
            path=path,
            json_type="unknown",
            required=required,
            nullable=False,
            analysis_status=SchemaAnalysisStatus.UNSUPPORTED,
            analysis_reason=reason,
            label_allowed=False,
            label_rejection_reason=reason,
            value_intents=(),
            cardinality_risk="unknown",
            warnings=(reason,),
        )

    def _effective_type(
        self,
        raw_type: Any,
    ) -> tuple[str, bool, Optional[str]]:
        """Resolve a simple type or simple nullable union without order bias."""
        supported = {"object", "array", *_SCALAR_TYPES}
        if isinstance(raw_type, str):
            if raw_type in supported:
                return raw_type, False, None
            return "unknown", False, f"Unsupported JSON type '{raw_type}'"
        if isinstance(raw_type, list):
            if any(not isinstance(item, str) for item in raw_type):
                return "unknown", False, "Type union contains a non-string member"
            members = set(raw_type)
            non_null = members - {"null"}
            if len(non_null) == 1 and len(members) == 2:
                effective = next(iter(non_null))
                if effective in supported:
                    return effective, True, None
            return "unknown", False, "Only one simple type plus null is supported"
        return "unknown", False, "JSON Schema field must declare an explicit type"

    def _numeric_bound_status(self, schema: dict[str, Any]) -> tuple[str, str]:
        """Classify the effective modern JSON Schema lower bound."""
        bounds: list[float] = []
        for keyword in ("minimum", "exclusiveMinimum"):
            if keyword not in schema:
                continue
            value = schema[keyword]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return "unsupported", f"{keyword} must be a finite JSON number"
            if not math.isfinite(float(value)):
                return "unsupported", f"{keyword} must be a finite JSON number"
            bounds.append(float(value))
        if not bounds or max(bounds) < 0.0:
            return "unsafe", "JSON Schema does not guarantee a non-negative value"
        return "safe", "JSON Schema guarantees a non-negative value"

    def _label_decision(
        self,
        *,
        path: str,
        json_type: str,
        nullable: bool,
        schema: dict[str, Any],
    ) -> tuple[bool, Optional[str], str]:
        """Apply the initial deterministic cardinality policy."""
        del nullable  # Nullability changes runtime absence, not cardinality proof.
        tail = path.replace("[*]", "").split(".")[-1]
        if _HIGH_CARDINALITY_NAME.search(tail):
            return False, "Field name indicates high cardinality", "high"
        if schema.get("format") in {
            "uuid",
            "email",
            "uri",
            "url",
            "date",
            "date-time",
            "time",
        }:
            return False, "Field format indicates high cardinality", "high"
        if json_type == "boolean":
            return True, None, "low"

        enum = schema.get("enum")
        if enum is not None:
            if not isinstance(enum, list):
                return False, "Enum must be an array", "unknown"
            if len(enum) > self.limits.max_enum_values:
                return (
                    False,
                    (
                        f"Enum exceeds configured label limit "
                        f"{self.limits.max_enum_values}"
                    ),
                    "high",
                )
            if not enum or any(
                value is None
                or isinstance(value, (dict, list))
                or not isinstance(value, (str, int, float, bool))
                or (isinstance(value, float) and not math.isfinite(value))
                for value in enum
            ):
                return False, "Enum contains a non-scalar label value", "high"
            return True, None, "low"

        if json_type in _SCALAR_TYPES:
            return False, "Free scalar values are not safe Builder labels", "high"
        return False, f"JSON type '{json_type}' cannot be a label", "high"

    def _validate_path_bounds(self, path: str) -> None:
        """Reject paths that exceed configured parser resource bounds."""
        if len(path) > self.limits.max_path_length:
            raise MetricBuilderSchemaAnalysisError(
                f"Schema path exceeds maximum length {self.limits.max_path_length}"
            )
        segments = path[2:].replace("[*]", "").split(".")
        if len(segments) > self.limits.max_path_segments:
            raise MetricBuilderSchemaAnalysisError(
                f"Schema path exceeds maximum segment count "
                f"{self.limits.max_path_segments}"
            )
