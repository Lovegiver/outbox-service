from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.metrics_engine.schema_graph import build_schema_graph
from app.metrics_engine.schema_path_resolver import (
    ResolvedPath,
    SchemaPathResolutionError,
    resolve_path,
)


ALLOWED_VALUE_TYPES = {"number", "integer"}


@dataclass(frozen=True)
class ValidatedObservation:
    code: str
    value_path: ResolvedPath
    labels: dict[str, ResolvedPath | str]


@dataclass(frozen=True)
class ValidatedMetricYaml:
    version: str
    observations: list[ValidatedObservation]


class MetricYamlValidationError(ValueError):
    pass


def validate_metric_yaml(
    metric_yaml: dict[str, Any],
    json_schema: dict[str, Any],
) -> ValidatedMetricYaml:
    version = metric_yaml.get("version")

    if version != "1.0":
        raise MetricYamlValidationError("Only metric YAML version '1.0' is supported")

    observations = metric_yaml.get("observations")

    if not isinstance(observations, list) or not observations:
        raise MetricYamlValidationError("'observations' must be a non-empty list")

    schema_graph = build_schema_graph(json_schema)

    validated_observations: list[ValidatedObservation] = []

    for observation in observations:
        validated_observations.append(
            _validate_observation(
                observation=observation,
                schema_graph=schema_graph,
            )
        )

    return ValidatedMetricYaml(
        version=version,
        observations=validated_observations,
    )


def _validate_observation(
    observation: Any,
    schema_graph,
) -> ValidatedObservation:
    if not isinstance(observation, dict):
        raise MetricYamlValidationError("Each observation must be an object")

    code = observation.get("code")
    value_path = observation.get("value_path")
    labels = observation.get("labels", {})

    if not isinstance(code, str) or not code:
        raise MetricYamlValidationError("Observation 'code' is required")

    if not isinstance(value_path, str) or not value_path:
        raise MetricYamlValidationError(
            f"Observation '{code}' must define a non-empty 'value_path'"
        )

    if not isinstance(labels, dict):
        raise MetricYamlValidationError(
            f"Observation '{code}' labels must be an object"
        )

    resolved_value_path = _resolve_required_path(
        path=value_path,
        schema_graph=schema_graph,
        context=f"Observation '{code}' value_path",
    )

    if resolved_value_path.json_type not in ALLOWED_VALUE_TYPES:
        raise MetricYamlValidationError(
            f"Observation '{code}' value_path must resolve to a numeric type, "
            f"got '{resolved_value_path.json_type}'"
        )

    validated_labels = _validate_labels(
        observation_code=code,
        labels=labels,
        schema_graph=schema_graph,
        value_path=resolved_value_path,
    )

    return ValidatedObservation(
        code=code,
        value_path=resolved_value_path,
        labels=validated_labels,
    )


def _validate_labels(
    observation_code: str,
    labels: dict,
    schema_graph,
    value_path: ResolvedPath,
) -> dict[str, ResolvedPath | str]:
    validated_labels: dict[str, ResolvedPath | str] = {}

    for label_name, label_path in labels.items():
        if not isinstance(label_name, str) or not label_name:
            raise MetricYamlValidationError(
                f"Observation '{observation_code}' contains an invalid label name"
            )

        if label_path == "$index":
            if value_path.iterator_path is None:
                raise MetricYamlValidationError(
                    f"Observation '{observation_code}' label '{label_name}' uses $index "
                    "but value_path does not iterate over an array"
                )

            validated_labels[label_name] = "$index"
            continue

        if not isinstance(label_path, str) or not label_path:
            raise MetricYamlValidationError(
                f"Observation '{observation_code}' label '{label_name}' "
                "must be a non-empty string path or '$index'"
            )

        resolved_label_path = _resolve_required_path(
            path=label_path,
            schema_graph=schema_graph,
            context=f"Observation '{observation_code}' label '{label_name}'",
        )

        _validate_iterator_alignment(
            observation_code=observation_code,
            label_name=label_name,
            value_path=value_path,
            label_path=resolved_label_path,
        )

        validated_labels[label_name] = resolved_label_path

    return validated_labels


def _validate_iterator_alignment(
    observation_code: str,
    label_name: str,
    value_path: ResolvedPath,
    label_path: ResolvedPath,
) -> None:
    if label_path.iterator_path is None:
        return

    if value_path.iterator_path is None:
        raise MetricYamlValidationError(
            f"Observation '{observation_code}' label '{label_name}' iterates over "
            f"'{label_path.iterator_path}' but value_path does not iterate"
        )

    if label_path.iterator_path != value_path.iterator_path:
        raise MetricYamlValidationError(
            f"Observation '{observation_code}' label '{label_name}' iterates over "
            f"'{label_path.iterator_path}' but value_path iterates over "
            f"'{value_path.iterator_path}'"
        )


def _resolve_required_path(
    path: str,
    schema_graph,
    context: str,
) -> ResolvedPath:
    try:
        resolved_path = resolve_path(schema_graph, path)
    except SchemaPathResolutionError as exc:
        raise MetricYamlValidationError(f"{context} is invalid: {exc}") from exc

    if not resolved_path.required:
        raise MetricYamlValidationError(
            f"{context} targets an optional JSON field: {path}"
        )

    return resolved_path