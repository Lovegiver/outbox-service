"""Deterministic static cardinality safeguards for Builder metric snapshots.

The service deliberately operates on compiled Builder plans and exact JSON
Schemas.  It is never used by the Event runtime and never inspects observed
data, Prometheus, observations, or metric state.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from app.metrics_engine.prometheus_renderer import (
    PrometheusRenderingError,
    normalize_prometheus_metric_name,
    validate_prometheus_business_label_name,
)
from app.services.metric_builder_schema_analyzer import (
    AnalyzedBuilderField,
    MetricBuilderAnalysisLimits,
    MetricBuilderSchemaAnalyzer,
)


class CardinalityDecision(str, Enum):
    """Closed severity used by API clients and lifecycle services."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class CardinalityDiagnostic:
    """One stable, structured explanation of a static safeguard decision."""

    code: str
    message: str
    location: Optional[str] = None
    details: Optional[dict[str, Any]] = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe public representation."""
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.location is not None:
            result["location"] = self.location
        if self.details is not None:
            result["details"] = self.details
        return result


@dataclass(frozen=True)
class MetricCardinalityBreakdown:
    """Bound and provenance for one final Prometheus metric identity."""

    metric_code: str
    prometheus_metric_name: str
    intent: str
    labels: tuple[dict[str, Any], ...]
    contribution: Optional[int]
    accepted: bool
    source_schema_definition_id: Optional[int]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe public representation."""
        return {
            "metric_code": self.metric_code,
            "prometheus_metric_name": self.prometheus_metric_name,
            "intent": self.intent,
            "labels": list(self.labels),
            "contribution": self.contribution,
            "accepted": self.accepted,
            "source_schema_definition_id": self.source_schema_definition_id,
        }


@dataclass(frozen=True)
class CardinalityAssessment:
    """Projected EventType series bound and its explainable diagnostics."""

    decision: CardinalityDecision
    budget_limit: int
    current_estimated_series: int
    candidate_contribution: Optional[int]
    replaced_contribution: int
    projected_estimated_series: Optional[int]
    remaining_budget: Optional[int]
    warnings: tuple[CardinalityDiagnostic, ...]
    errors: tuple[CardinalityDiagnostic, ...]
    metric_breakdown: tuple[MetricCardinalityBreakdown, ...]

    @property
    def accepted(self) -> bool:
        """Whether this snapshot is statically safe to persist or activate."""
        return self.decision is not CardinalityDecision.ERROR

    def as_dict(self) -> dict[str, Any]:
        """Return the shared API representation for preview and creation."""
        return {
            "decision": self.decision.value,
            "budget_limit": self.budget_limit,
            "current_estimated_series": self.current_estimated_series,
            "candidate_contribution": self.candidate_contribution,
            "replaced_contribution": self.replaced_contribution,
            "projected_estimated_series": self.projected_estimated_series,
            "remaining_budget": self.remaining_budget,
            "warnings": [item.as_dict() for item in self.warnings],
            "errors": [item.as_dict() for item in self.errors],
            "metric_breakdown": [item.as_dict() for item in self.metric_breakdown],
        }


@dataclass(frozen=True)
class CardinalityPlan:
    """Compiled plan plus its exact schema identity for static analysis."""

    compiled_plan_json: dict[str, Any]
    schema_definition_id: Optional[int]
    json_schema: dict[str, Any]


class MetricCardinalityService:
    """Estimate a bounded Counter snapshot without consulting runtime data."""

    def __init__(
        self,
        analyzer: MetricBuilderSchemaAnalyzer,
        limits: MetricBuilderAnalysisLimits,
    ) -> None:
        """Initialize with the exact analyzer and application limits in use."""
        self.analyzer = analyzer
        self.limits = limits

    def assess(
        self,
        *,
        current_plans: Iterable[CardinalityPlan],
        candidate_plans: Iterable[CardinalityPlan],
        replaced_plans: Iterable[CardinalityPlan] = (),
    ) -> CardinalityAssessment:
        """Return a conservative projected EventType series bound.

        ``replaced_plans`` models active snapshots removed by the atomic
        activation.  This prevents a candidate from being double-counted with
        the active snapshot it replaces.
        """
        current = self._analyze_many(current_plans)
        candidate = self._analyze_many(candidate_plans)
        replaced = self._analyze_many(replaced_plans)
        errors = list(current[1]) + list(candidate[1]) + list(replaced[1])
        warnings: list[CardinalityDiagnostic] = []
        breakdown = tuple(current[2] + candidate[2])
        names: dict[str, str] = {}
        for item in breakdown:
            first_code = names.get(item.prometheus_metric_name)
            if first_code is not None and first_code != item.metric_code:
                errors.append(
                    CardinalityDiagnostic(
                        code="BUILDER_PROMETHEUS_NAME_COLLISION",
                        message="Metric codes collide after Prometheus normalization",
                        details={
                            "first_metric_code": first_code,
                            "second_metric_code": item.metric_code,
                            "prometheus_metric_name": item.prometheus_metric_name,
                        },
                    )
                )
            names[item.prometheus_metric_name] = item.metric_code
        current_total = current[0]
        candidate_total = candidate[0]
        replaced_total = replaced[0]

        if errors:
            return CardinalityAssessment(
                decision=CardinalityDecision.ERROR,
                budget_limit=self.limits.event_type_series_budget,
                current_estimated_series=current_total,
                candidate_contribution=None,
                replaced_contribution=replaced_total,
                projected_estimated_series=None,
                remaining_budget=None,
                warnings=tuple(warnings),
                errors=tuple(errors),
                metric_breakdown=breakdown,
            )

        projected = current_total - replaced_total + candidate_total
        if projected < 0:
            errors.append(
                CardinalityDiagnostic(
                    code="BUILDER_CARDINALITY_INCONSISTENT_SNAPSHOT",
                    message="The active metric snapshot cannot be projected safely",
                )
            )
        elif projected > self.limits.event_type_series_budget:
            errors.append(
                CardinalityDiagnostic(
                    code="BUILDER_CARDINALITY_BUDGET_EXCEEDED",
                    message="Projected metric series exceed the EventType budget",
                    details={
                        "budget_limit": self.limits.event_type_series_budget,
                        "projected_estimated_series": projected,
                    },
                )
            )
        elif projected >= self.limits.event_type_series_warning:
            warnings.append(
                CardinalityDiagnostic(
                    code="BUILDER_CARDINALITY_BUDGET_WARNING",
                    message="Projected metric series are close to the EventType budget",
                    details={
                        "budget_limit": self.limits.event_type_series_budget,
                        "projected_estimated_series": projected,
                    },
                )
            )

        return CardinalityAssessment(
            decision=(
                CardinalityDecision.ERROR
                if errors
                else CardinalityDecision.WARNING
                if warnings
                else CardinalityDecision.INFO
            ),
            budget_limit=self.limits.event_type_series_budget,
            current_estimated_series=current_total,
            candidate_contribution=candidate_total,
            replaced_contribution=replaced_total,
            projected_estimated_series=projected if not errors else None,
            remaining_budget=(
                max(0, self.limits.event_type_series_budget - projected)
                if not errors
                else None
            ),
            warnings=tuple(warnings),
            errors=tuple(errors),
            metric_breakdown=breakdown,
        )

    def _analyze_many(
        self,
        plans: Iterable[CardinalityPlan],
    ) -> tuple[
        int, tuple[CardinalityDiagnostic, ...], list[MetricCardinalityBreakdown]
    ]:
        """Estimate every observation in a deterministic snapshot order."""
        total = 0
        errors: list[CardinalityDiagnostic] = []
        breakdown: list[MetricCardinalityBreakdown] = []
        seen_names: dict[str, str] = {}
        for plan in plans:
            fields = {
                field.path: field for field in self.analyzer.analyze(plan.json_schema)
            }
            observations = plan.compiled_plan_json.get("observations", [])
            if not isinstance(observations, list):
                errors.append(
                    CardinalityDiagnostic(
                        code="BUILDER_CARDINALITY_UNBOUNDED",
                        message="Compiled metric plan has an unsupported observation shape",
                    )
                )
                continue
            for observation in observations:
                item, item_errors = self._analyze_observation(
                    observation=observation,
                    fields=fields,
                    schema_definition_id=plan.schema_definition_id,
                )
                breakdown.append(item)
                errors.extend(item_errors)
                if item.contribution is not None:
                    total = self._safe_add(total, item.contribution, errors)
                other_code = seen_names.get(item.prometheus_metric_name)
                if other_code is not None and other_code != item.metric_code:
                    errors.append(
                        CardinalityDiagnostic(
                            code="BUILDER_PROMETHEUS_NAME_COLLISION",
                            message="Metric codes collide after Prometheus normalization",
                            details={
                                "first_metric_code": other_code,
                                "second_metric_code": item.metric_code,
                                "prometheus_metric_name": item.prometheus_metric_name,
                            },
                        )
                    )
                seen_names[item.prometheus_metric_name] = item.metric_code
        return total, tuple(errors), breakdown

    def _analyze_observation(
        self,
        *,
        observation: Any,
        fields: dict[str, AnalyzedBuilderField],
        schema_definition_id: Optional[int],
    ) -> tuple[MetricCardinalityBreakdown, list[CardinalityDiagnostic]]:
        """Estimate one compiled observation without accepting unknown labels."""
        errors: list[CardinalityDiagnostic] = []
        if not isinstance(observation, dict):
            item = MetricCardinalityBreakdown(
                "unknown", "unknown", "unknown", (), None, False, schema_definition_id
            )
            return item, [
                CardinalityDiagnostic(
                    "BUILDER_CARDINALITY_UNBOUNDED", "Compiled observation is invalid"
                )
            ]
        code = observation.get("metric_code")
        transform = observation.get("transform")
        if not isinstance(code, str) or not code or not isinstance(transform, str):
            item = MetricCardinalityBreakdown(
                "unknown", "unknown", "unknown", (), None, False, schema_definition_id
            )
            return item, [
                CardinalityDiagnostic(
                    "BUILDER_CARDINALITY_UNBOUNDED",
                    "Compiled observation lacks a metric identity",
                )
            ]
        final_name = normalize_prometheus_metric_name(code)
        labels = observation.get("labels", [])
        if not isinstance(labels, list):
            labels = []
            errors.append(
                CardinalityDiagnostic(
                    "BUILDER_CARDINALITY_UNBOUNDED", "Compiled labels are invalid", code
                )
            )
        contribution = 1
        label_breakdown: list[dict[str, Any]] = []
        seen_labels: set[str] = set()
        for label in labels:
            if not isinstance(label, dict):
                errors.append(
                    CardinalityDiagnostic(
                        "BUILDER_CARDINALITY_UNBOUNDED",
                        "Compiled label is invalid",
                        code,
                    )
                )
                continue
            name = label.get("name")
            path = label.get("path")
            if not isinstance(name, str) or not isinstance(path, str):
                errors.append(
                    CardinalityDiagnostic(
                        "BUILDER_CARDINALITY_UNBOUNDED",
                        "Compiled label lacks an identity",
                        code,
                    )
                )
                continue
            try:
                validate_prometheus_business_label_name(name)
            except PrometheusRenderingError:
                errors.append(
                    CardinalityDiagnostic(
                        "BUILDER_PROMETHEUS_LABEL_COLLISION",
                        "Label name is invalid or collides with an OB1 technical label",
                        name,
                    )
                )
                continue
            if name in seen_labels:
                errors.append(
                    CardinalityDiagnostic(
                        "BUILDER_PROMETHEUS_LABEL_COLLISION",
                        "Multiple labels have the same Prometheus name",
                        name,
                    )
                )
                continue
            seen_labels.add(name)
            field = fields.get(path)
            if (
                field is None
                or not field.label_allowed
                or field.label_cardinality is None
            ):
                errors.append(
                    CardinalityDiagnostic(
                        "BUILDER_CARDINALITY_UNBOUNDED",
                        "Label cardinality cannot be demonstrated statically",
                        path,
                    )
                )
                label_breakdown.append(
                    {"name": name, "path": path, "cardinality": None, "source": None}
                )
                continue
            contribution = self._safe_multiply(
                contribution, field.label_cardinality, errors
            )
            label_breakdown.append(
                {
                    "name": name,
                    "path": path,
                    "cardinality": field.label_cardinality,
                    "source": field.label_cardinality_source,
                }
            )
        return (
            MetricCardinalityBreakdown(
                metric_code=code,
                prometheus_metric_name=final_name,
                intent=transform,
                labels=tuple(label_breakdown),
                contribution=contribution if not errors else None,
                accepted=not errors,
                source_schema_definition_id=schema_definition_id,
            ),
            errors,
        )

    def _safe_multiply(
        self, left: int, right: int, errors: list[CardinalityDiagnostic]
    ) -> int:
        """Multiply bounded cardinalities without allowing a low overflow result."""
        if right <= 0 or left > self.limits.max_metric_series_estimate // right:
            errors.append(
                CardinalityDiagnostic(
                    "BUILDER_CARDINALITY_UNBOUNDED",
                    "Metric label cardinality exceeds the configured safety bound",
                )
            )
            return self.limits.max_metric_series_estimate
        return left * right

    def _safe_add(
        self, left: int, right: int, errors: list[CardinalityDiagnostic]
    ) -> int:
        """Add contributions while retaining conservative failure semantics."""
        if right < 0 or left > self.limits.max_metric_series_estimate - right:
            errors.append(
                CardinalityDiagnostic(
                    "BUILDER_CARDINALITY_UNBOUNDED",
                    "Metric snapshot cardinality exceeds the configured safety bound",
                )
            )
            return self.limits.max_metric_series_estimate
        return left + right
