from __future__ import annotations

from dataclasses import dataclass

from app.metrics_engine.metric_yaml_validator import ValidatedMetricYaml


@dataclass(frozen=True)
class CompiledProcessingPlan:
    """
    Runtime-ready analytical processing plan.
    """

    processing_chain_id: int
    metric_definition_id: int
    metric_definition_version_id: int
    validated_metric_yaml: ValidatedMetricYaml