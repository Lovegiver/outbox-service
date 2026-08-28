"""Unit tests for conservative Metrics Builder schema analysis."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.services.config_service import ConfigService
from app.services.metric_builder_schema_analyzer import (
    MetricBuilderAnalysisLimits,
    MetricBuilderSchemaAnalysisError,
    MetricBuilderSchemaAnalyzer,
    SchemaAnalysisStatus,
)


@pytest.fixture
def analyzer() -> MetricBuilderSchemaAnalyzer:
    """Return an analyzer with intentionally small, testable limits."""
    return MetricBuilderSchemaAnalyzer(
        MetricBuilderAnalysisLimits(
            max_enum_values=3,
            max_schema_depth=4,
            max_schema_fields=10,
        )
    )


def test_application_exposes_configurable_builder_limits() -> None:
    limits = ConfigService("test").get_metric_builder_limits()

    assert limits == {
        "max_enum_values": 20,
        "max_labels": 5,
        "max_path_length": 512,
        "max_path_segments": 32,
        "max_schema_depth": 32,
        "max_schema_fields": 1000,
        "max_label_name_length": 128,
    }


def _object(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
    }


def test_nested_required_requires_every_ancestor(
    analyzer: MetricBuilderSchemaAnalyzer,
) -> None:
    schema = _object(
        {
            "required_parent": _object(
                {"required_leaf": {"type": "string"}}, ["required_leaf"]
            ),
            "optional_parent": _object(
                {"required_leaf": {"type": "string"}}, ["required_leaf"]
            ),
        },
        ["required_parent"],
    )

    fields = {field.path: field for field in analyzer.analyze(schema)}

    assert fields["$.required_parent.required_leaf"].required is True
    assert fields["$.optional_parent.required_leaf"].required is False


@pytest.mark.parametrize(
    ("raw_type", "nullable", "json_type"),
    [
        (["string", "null"], True, "string"),
        (["null", "string"], True, "string"),
        ("string", False, "string"),
    ],
)
def test_nullable_is_order_independent_and_distinct_from_required(
    analyzer: MetricBuilderSchemaAnalyzer,
    raw_type: object,
    nullable: bool,
    json_type: str,
) -> None:
    [field] = analyzer.analyze(_object({"value": {"type": raw_type}}, ["value"]))

    assert field.required is True
    assert field.nullable is nullable
    assert field.json_type == json_type


def test_nullable_ancestor_makes_nested_value_nullable(
    analyzer: MetricBuilderSchemaAnalyzer,
) -> None:
    schema = _object(
        {
            "payload": {
                "type": ["object", "null"],
                "required": ["amount"],
                "properties": {"amount": {"type": "number", "minimum": 0}},
            }
        },
        ["payload"],
    )

    [field] = analyzer.analyze(schema)

    assert field.path == "$.payload.amount"
    assert field.required is True
    assert field.nullable is True


@pytest.mark.parametrize(
    ("field_schema", "status", "intents"),
    [
        ({"type": "integer", "minimum": 0}, "SUPPORTED", ("sum_value",)),
        ({"type": "number", "minimum": 5}, "SUPPORTED", ("sum_value",)),
        ({"type": "number", "exclusiveMinimum": 0}, "SUPPORTED", ("sum_value",)),
        (
            {"type": "number", "minimum": -1, "exclusiveMinimum": 0},
            "SUPPORTED",
            ("sum_value",),
        ),
        ({"type": "number", "minimum": -1}, "UNSAFE", ()),
        ({"type": "integer"}, "UNSAFE", ()),
        ({"type": "number", "minimum": float("nan")}, "UNSUPPORTED", ()),
        ({"type": "number", "exclusiveMinimum": True}, "UNSUPPORTED", ()),
        (
            {"type": "array", "items": {"type": "string"}},
            "SUPPORTED",
            ("count_array_items",),
        ),
        ({"type": "string"}, "SUPPORTED", ("measure_string_length",)),
        ({"type": "boolean"}, "SUPPORTED", ("count_boolean_true",)),
    ],
)
def test_counter_intents_are_derived_from_type_and_bounds(
    analyzer: MetricBuilderSchemaAnalyzer,
    field_schema: dict,
    status: str,
    intents: tuple[str, ...],
) -> None:
    fields = analyzer.analyze(_object({"value": field_schema}))
    field = next(item for item in fields if item.path == "$.value")

    assert field.analysis_status.value == status
    assert field.value_intents == intents


@pytest.mark.parametrize(
    "field_schema",
    [
        {"type": ["string", "number"]},
        {"type": "string", "anyOf": [{"type": "string"}]},
        {"$ref": "#/$defs/value"},
        {"oneOf": [{"type": "string"}, {"type": "boolean"}]},
        {"allOf": [{"type": "string"}]},
    ],
)
def test_complex_constructions_are_explicitly_unsupported(
    analyzer: MetricBuilderSchemaAnalyzer,
    field_schema: dict,
) -> None:
    [field] = analyzer.analyze(_object({"value": field_schema}))

    assert field.analysis_status is SchemaAnalysisStatus.UNSUPPORTED
    assert field.value_intents == ()
    assert field.label_allowed is False


@pytest.mark.parametrize(
    ("name", "field_schema", "allowed"),
    [
        ("active", {"type": "boolean"}, True),
        ("status", {"type": "string", "enum": ["a", "b", "c"]}, True),
        ("status", {"type": "string", "enum": ["a", "b", "c", "d"]}, False),
        ("status", {"type": "string", "enum": ["a", None]}, False),
        ("status", {"type": "string", "enum": ["a", {}]}, False),
        ("customer_id", {"type": "string", "enum": ["a"]}, False),
        ("contact", {"type": "string", "format": "email", "enum": ["a"]}, False),
        ("title", {"type": "string"}, False),
        ("amount", {"type": "number", "minimum": 0}, False),
    ],
)
def test_static_label_policy(
    analyzer: MetricBuilderSchemaAnalyzer,
    name: str,
    field_schema: dict,
    allowed: bool,
) -> None:
    [field] = analyzer.analyze(_object({name: field_schema}))

    assert field.label_allowed is allowed
    assert (field.label_rejection_reason is None) is allowed


@pytest.mark.parametrize(("size", "allowed"), [(2, True), (3, True), (4, False)])
def test_enum_label_limit_boundaries(
    analyzer: MetricBuilderSchemaAnalyzer,
    size: int,
    allowed: bool,
) -> None:
    [field] = analyzer.analyze(
        _object({"status": {"type": "string", "enum": list(range(size))}})
    )

    assert field.label_allowed is allowed


def test_literal_missing_string_is_not_reserved(
    analyzer: MetricBuilderSchemaAnalyzer,
) -> None:
    [field] = analyzer.analyze(
        _object({"status": {"type": "string", "enum": ["__missing__"]}})
    )

    assert field.label_allowed is True


def test_analysis_does_not_mutate_input(analyzer: MetricBuilderSchemaAnalyzer) -> None:
    schema = _object(
        {
            "status": {"type": "string", "enum": ["new", "done"]},
            "items": {"type": "array", "items": {"type": "boolean"}},
        }
    )
    original = deepcopy(schema)

    analyzer.analyze(schema)

    assert schema == original


def test_schema_depth_is_bounded() -> None:
    analyzer = MetricBuilderSchemaAnalyzer(
        MetricBuilderAnalysisLimits(max_schema_depth=1)
    )
    schema = _object({"parent": _object({"leaf": {"type": "string"}})})

    with pytest.raises(MetricBuilderSchemaAnalysisError, match="maximum depth"):
        analyzer.analyze(schema)


def test_schema_field_count_is_bounded() -> None:
    analyzer = MetricBuilderSchemaAnalyzer(
        MetricBuilderAnalysisLimits(max_schema_fields=1)
    )
    schema = _object({"first": {"type": "string"}, "second": {"type": "string"}})

    with pytest.raises(MetricBuilderSchemaAnalysisError, match="field count"):
        analyzer.analyze(schema)


def test_unsupported_property_name_is_reported_not_interpreted(
    analyzer: MetricBuilderSchemaAnalyzer,
) -> None:
    [field] = analyzer.analyze(_object({"value[?(@.x)]": {"type": "string"}}))

    assert field.analysis_status is SchemaAnalysisStatus.UNSUPPORTED
    assert "path grammar" in field.analysis_reason
