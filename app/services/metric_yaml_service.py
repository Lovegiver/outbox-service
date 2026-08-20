from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.metrics_engine.metric_plan_compiler import compile_metric_yaml_to_json
from app.metrics_engine.metric_yaml_parser import parse_metric_yaml
from app.metrics_engine.metric_yaml_validator import validate_metric_yaml


@dataclass(frozen=True)
class MetricYamlCompilation:
    """Validated YAML and its deterministic compiled runtime preview."""

    metric_yaml: dict[str, Any]
    compiled_plan_json: dict[str, Any]


class MetricYamlService:
    """Single parsing, validation, and compilation path for metric YAML."""

    def compile(
        self,
        yaml_content: str,
        json_schema: dict[str, Any],
    ) -> MetricYamlCompilation:
        """Parse, validate, and compile YAML without persisting any data."""
        metric_yaml = parse_metric_yaml(yaml_content)
        validated_metric_yaml = validate_metric_yaml(
            metric_yaml=metric_yaml,
            json_schema=json_schema,
        )
        compiled_plan_json = compile_metric_yaml_to_json(validated_metric_yaml)

        return MetricYamlCompilation(
            metric_yaml=metric_yaml,
            compiled_plan_json=compiled_plan_json,
        )
