from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonpath_ng import parse

from app.metrics_engine.metric_yaml_validator import ValidatedMetricYaml
from app.metrics_engine.observation import DimensionValue, Observation


class ObservationExtractionError(ValueError):
    pass

@dataclass(frozen=True)
class ExtractionLimits:
    max_observations_per_event: int = 1000
    max_matches_per_observation: int = 200


def extract_observations(
    payload: dict[str, Any],
    metric_yaml: ValidatedMetricYaml,
    limits: ExtractionLimits | None = None,
) -> list[Observation]:

    observations: list[Observation] = []
    effective_limits = limits or ExtractionLimits()

    for observation_definition in metric_yaml.observations:
        value_matches = parse(observation_definition.value_path.path).find(payload)

        if not value_matches:
            raise ObservationExtractionError(
                f"No value found for observation '{observation_definition.code}' "
                f"at path '{observation_definition.value_path.path}'"
            )

        if len(value_matches) > effective_limits.max_matches_per_observation:
            raise ObservationExtractionError(
                f"Observation '{observation_definition.code}' produced "
                f"{len(value_matches)} matches, exceeding limit "
                f"{effective_limits.max_matches_per_observation}"
            )

        label_matches_by_name = _extract_label_matches_by_name(
            payload=payload,
            observation_definition=observation_definition,
        )

        for index, match in enumerate(value_matches):
            dimensions = _build_dimensions(
                index=index,
                label_matches_by_name=label_matches_by_name,
                observation_code=observation_definition.code,
            )

            if len(observations) >= effective_limits.max_observations_per_event:
                raise ObservationExtractionError(
                    f"Event produced more than "
                    f"{effective_limits.max_observations_per_event} observations"
                )

            observations.append(
                Observation(
                    metric_code=observation_definition.code,
                    value=_to_float(
                        value=match.value,
                        observation_code=observation_definition.code,
                    ),
                    dimensions=dimensions,
                )
            )

    return observations


def _extract_label_matches_by_name(
    payload: dict[str, Any],
    observation_definition,
) -> dict[str, list[Any] | str]:
    label_matches_by_name: dict[str, list[Any] | str] = {}

    for label_name, label_path in observation_definition.labels.items():
        if label_path == "$index":
            label_matches_by_name[label_name] = "$index"
            continue

        matches = parse(label_path.path).find(payload)

        if not matches:
            raise ObservationExtractionError(
                f"No value found for observation '{observation_definition.code}' "
                f"label '{label_name}' at path '{label_path.path}'"
            )

        label_matches_by_name[label_name] = [match.value for match in matches]

    return label_matches_by_name


def _build_dimensions(
    index: int,
    label_matches_by_name: dict[str, list[Any] | str],
    observation_code: str,
) -> dict[str, DimensionValue]:
    dimensions: dict[str, DimensionValue] = {}

    for label_name, label_values in label_matches_by_name.items():
        if label_values == "$index":
            dimensions[label_name] = index
            continue

        if index >= len(label_values):
            raise ObservationExtractionError(
                f"Observation '{observation_code}' label '{label_name}' has no value "
                f"for index {index}"
            )

        dimensions[label_name] = _to_dimension_value(
            value=label_values[index],
            observation_code=observation_code,
            label_name=label_name,
        )

    return dimensions


def _to_float(value: Any, observation_code: str) -> float:
    if isinstance(value, bool):
        raise ObservationExtractionError(
            f"Observation '{observation_code}' value must be numeric, got boolean"
        )

    if not isinstance(value, int | float):
        raise ObservationExtractionError(
            f"Observation '{observation_code}' value must be numeric, "
            f"got {type(value).__name__}"
        )

    return float(value)


def _to_dimension_value(
    value: Any,
    observation_code: str,
    label_name: str,
) -> DimensionValue:
    if isinstance(value, str | int | float | bool):
        return value

    raise ObservationExtractionError(
        f"Observation '{observation_code}' label '{label_name}' must resolve to a scalar value, "
        f"got {type(value).__name__}"
    )
