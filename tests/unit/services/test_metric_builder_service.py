"""Unit tests for BDD-016A Builder intent contracts."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.models.metric_definition import MetricDefinition
from app.models.schema_definition import SchemaDefinition
from app.services.metric_builder_errors import (
    MetricBuilderNotFoundError,
    MetricBuilderScopeError,
)
from app.services.metric_builder_schema_analyzer import (
    MetricBuilderAnalysisLimits,
    MetricBuilderSchemaAnalyzer,
)
from app.services.metric_builder_service import MetricBuilderService
from app.services.metric_yaml_service import MetricYamlService

SCHEMA = {
    "type": "object",
    "required": ["amount", "items", "title", "active", "status"],
    "properties": {
        "amount": {"type": "number", "minimum": 0},
        "unsafe_amount": {"type": "number"},
        "items": {"type": "array", "items": {"type": "string"}},
        "title": {"type": "string"},
        "active": {"type": "boolean"},
        "status": {"type": "string", "enum": ["new", "done"]},
        "customer_id": {"type": "string", "enum": ["a", "b"]},
        "complex": {"anyOf": [{"type": "string"}, {"type": "boolean"}]},
    },
}


def _service(schema: dict = SCHEMA) -> tuple[MetricBuilderService, Mock, Mock]:
    db = Mock()
    event_type_repository = Mock()
    schema_repository = Mock()
    schema_repository.find_active_by_event_type.return_value = SchemaDefinition(
        id=7,
        event_type_id=12,
        json_version_internal="1.0",
        json_schema=schema,
        is_active=True,
    )
    definition_repository = Mock()
    definition_repository.list_by_event_type.return_value = []
    limits = MetricBuilderAnalysisLimits(max_enum_values=3, max_labels=2)
    service = MetricBuilderService(
        db=db,
        event_type_repository=event_type_repository,
        schema_repository=schema_repository,
        metric_definition_repository=definition_repository,
        metric_definition_version_repository=Mock(),
        compatibility_repository=Mock(),
        metric_yaml_service=MetricYamlService(),
        schema_analyzer=MetricBuilderSchemaAnalyzer(limits),
        limits=limits,
    )
    return service, schema_repository, definition_repository


@pytest.mark.parametrize(
    ("intent", "path", "labels", "transform"),
    [
        ("count_event", None, {}, "constant"),
        ("count_by_label", None, {"status": "$.status"}, "constant"),
        ("sum_value", "$.amount", {}, "identity"),
        ("count_array_items", "$.items", {}, "count"),
        ("measure_string_length", "$.title", {}, "length"),
        ("count_boolean_true", "$.active", {}, "to_number"),
    ],
)
def test_six_intents_compile_to_exact_runtime_transforms(
    intent: str,
    path: str | None,
    labels: dict[str, str],
    transform: str,
) -> None:
    service, _, _ = _service()

    preview = service.preview_metric(12, "sales-total", intent, path, labels)

    assert preview.valid is True
    assert preview.prometheus_metric_name == "ob1_sales_total"
    assert preview.compiled_plan_json is not None
    observation = preview.compiled_plan_json["observations"][0]
    assert observation["transform"] == transform
    assert preview.compiled_plan_json["compiler_version"] == "1.1"


@pytest.mark.parametrize(
    ("intent", "path", "labels", "error"),
    [
        ("count_event", "$.amount", {}, "neither value_path nor labels"),
        ("count_event", None, {"status": "$.status"}, "neither value_path nor labels"),
        ("count_by_label", None, {}, "exactly one label"),
        (
            "count_by_label",
            None,
            {"a": "$.status", "b": "$.active"},
            "exactly one label",
        ),
        ("sum_value", None, {}, "requires one value_path"),
        ("sum_value", "$.title", {}, "incompatible"),
        ("sum_value", "$.unsafe_amount", {}, "does not guarantee"),
        ("count_by_label", None, {"id": "$.customer_id"}, "high cardinality"),
        ("count_by_label", None, {"status": "$.title"}, "Free scalar"),
        ("count_boolean_true", "$.missing", {}, "canonical field"),
        ("count_boolean_true", "$.active[?(@.x)]", {}, "canonical field"),
        ("count_boolean_true", "$.complex", {}, "Complex JSON Schema"),
    ],
)
def test_invalid_builder_contract_returns_stable_negative_preview(
    intent: str,
    path: str | None,
    labels: dict[str, str],
    error: str,
) -> None:
    service, _, _ = _service()

    preview = service.preview_metric(12, "metric", intent, path, labels)

    assert preview.valid is False
    assert preview.yaml_content is None
    assert preview.compiled_plan_json is None
    assert error in preview.errors[0]
    assert preview.errors[0].startswith("BUILDER_")


@pytest.mark.parametrize(
    "metric_code",
    ["", "line\nbreak", "bad code", "' OR 1=1 --", "x" * 151],
)
def test_metric_code_uses_positive_bounded_grammar(metric_code: str) -> None:
    service, _, _ = _service()

    preview = service.preview_metric(12, metric_code, "count_event", None, {})

    assert preview.valid is False
    assert "BUILDER_CONTRACT_INVALID" in preview.errors[0]


def test_normalized_prometheus_collision_is_rejected() -> None:
    service, _, definition_repository = _service()
    definition_repository.list_by_event_type.return_value = [
        MetricDefinition(event_type_id=12, code="sales_total", name="Sales")
    ]

    preview = service.preview_metric(12, "sales-total", "count_event", None, {})

    assert preview.valid is False
    assert preview.errors[0].startswith("BUILDER_PROMETHEUS_NAME_COLLISION")


def test_existing_ob1_prefix_collision_is_rejected() -> None:
    service, _, definition_repository = _service()
    definition_repository.list_by_event_type.return_value = [
        MetricDefinition(event_type_id=12, code="sales", name="Sales")
    ]

    preview = service.preview_metric(12, "ob1_sales", "count_event", None, {})

    assert preview.valid is False
    assert "COLLISION" in preview.errors[0]


def test_unexpected_compiler_error_is_not_masked_as_invalid_preview() -> None:
    service, _, _ = _service()
    service.metric_yaml_service.compile = Mock(side_effect=RuntimeError("internal"))

    with pytest.raises(RuntimeError, match="internal"):
        service.preview_metric(12, "metric", "count_event", None, {})


def test_missing_and_out_of_scope_schemas_are_narrow_errors() -> None:
    service, schema_repository, _ = _service()
    schema_repository.find_by_id.return_value = None
    with pytest.raises(MetricBuilderNotFoundError):
        service.list_schema_fields(12, 999)

    schema_repository.find_by_id.return_value = SchemaDefinition(
        id=8,
        event_type_id=13,
        json_version_internal="1.0",
        json_schema=SCHEMA,
    )
    with pytest.raises(MetricBuilderScopeError):
        service.list_schema_fields(12, 8)


def test_preview_is_read_only() -> None:
    service, _, definition_repository = _service()

    preview = service.preview_metric(12, "events", "count_event", None, {})

    assert preview.valid is True
    definition_repository.add.assert_not_called()
    service.metric_definition_version_repository.add.assert_not_called()
    service.compatibility_repository.add.assert_not_called()
    service.db.commit.assert_not_called()
