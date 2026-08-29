"""Unit tests for static, explainable EventType cardinality budgeting."""

from __future__ import annotations

from app.services.metric_builder_schema_analyzer import (
    MetricBuilderAnalysisLimits,
    MetricBuilderSchemaAnalyzer,
)
from app.services.metric_cardinality_service import (
    CardinalityDecision,
    CardinalityPlan,
    MetricCardinalityService,
)


def _service(*, budget: int = 200, warning: int = 160) -> MetricCardinalityService:
    """Build a small deterministic estimator."""
    limits = MetricBuilderAnalysisLimits(
        event_type_series_budget=budget,
        event_type_series_warning=warning,
        max_metric_series_estimate=10_000,
    )
    return MetricCardinalityService(MetricBuilderSchemaAnalyzer(limits), limits)


def _schema() -> dict:
    return {
        "type": "object",
        "required": ["active", "status"],
        "properties": {
            "active": {"type": "boolean"},
            "status": {"type": "string", "enum": ["new", "paid", "sent"]},
            "optional_status": {"type": "string", "enum": ["new", "paid"]},
        },
    }


def _plan(code: str, labels: list[dict] | None = None) -> CardinalityPlan:
    return CardinalityPlan(
        compiled_plan_json={
            "observations": [
                {"metric_code": code, "transform": "constant", "labels": labels or []}
            ]
        },
        schema_definition_id=1,
        json_schema=_schema(),
    )


def _label(name: str, path: str) -> dict:
    return {"name": name, "path": path}


def test_metric_without_dynamic_label_contributes_one_series() -> None:
    assessment = _service().assess(current_plans=[], candidate_plans=[_plan("events")])

    assert assessment.decision is CardinalityDecision.INFO
    assert assessment.candidate_contribution == 1
    assert assessment.projected_estimated_series == 1


def test_multiple_bounded_labels_multiply_their_domains() -> None:
    assessment = _service().assess(
        current_plans=[],
        candidate_plans=[
            _plan(
                "events", [_label("active", "$.active"), _label("status", "$.status")]
            )
        ],
    )

    assert assessment.candidate_contribution == 6
    assert assessment.metric_breakdown[0].labels[0]["cardinality"] == 2
    assert assessment.metric_breakdown[0].labels[1]["cardinality"] == 3


def test_optional_label_adds_one_omitted_prometheus_identity() -> None:
    assessment = _service().assess(
        current_plans=[],
        candidate_plans=[_plan("events", [_label("status", "$.optional_status")])],
    )

    assert assessment.candidate_contribution == 3
    assert assessment.metric_breakdown[0].labels[0]["source"] == "enum+ omitted"


def test_replaced_active_snapshot_is_not_double_counted() -> None:
    current = _plan("old", [_label("status", "$.status")])
    assessment = _service().assess(
        current_plans=[current],
        replaced_plans=[current],
        candidate_plans=[_plan("new", [_label("active", "$.active")])],
    )

    assert assessment.current_estimated_series == 3
    assert assessment.replaced_contribution == 3
    assert assessment.projected_estimated_series == 2


def test_exact_budget_is_allowed_and_excess_is_explained() -> None:
    accepted = _service(budget=3, warning=3).assess(
        current_plans=[],
        candidate_plans=[_plan("events", [_label("status", "$.status")])],
    )
    refused = _service(budget=2, warning=2).assess(
        current_plans=[],
        candidate_plans=[_plan("events", [_label("status", "$.status")])],
    )

    assert accepted.decision is CardinalityDecision.WARNING
    assert refused.decision is CardinalityDecision.ERROR
    assert refused.errors[0].code == "BUILDER_CARDINALITY_BUDGET_EXCEEDED"


def test_free_scalar_and_reserved_technical_label_are_rejected() -> None:
    schema = _schema()
    schema["properties"]["free"] = {"type": "string"}
    plan = CardinalityPlan(
        compiled_plan_json={
            "observations": [
                {
                    "metric_code": "events",
                    "transform": "constant",
                    "labels": [_label("ob1_project", "$.free")],
                }
            ]
        },
        schema_definition_id=1,
        json_schema=schema,
    )

    assessment = _service().assess(current_plans=[], candidate_plans=[plan])

    assert assessment.decision is CardinalityDecision.ERROR
    assert assessment.errors[0].code == "BUILDER_PROMETHEUS_LABEL_COLLISION"
