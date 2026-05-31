from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetricSample:
    name: str
    type: str
    help: str
    value: float
    labels: dict[str, str]


class MetricExtractionError(Exception):
    pass


def resolve_json_path(data: dict[str, Any], path: str) -> Any:
    if not path.startswith("$."):
        raise MetricExtractionError(f"Invalid JSON path: {path}")

    current: Any = data

    for part in path[2:].split("."):
        if not isinstance(current, dict):
            raise MetricExtractionError(f"Cannot access '{part}' in non-object value")

        if part not in current:
            raise MetricExtractionError(f"Missing JSON path part: {part} in {path}")

        current = current[part]

    return current


def resolve_value(data: dict[str, Any], value_definition: Any) -> Any:
    if isinstance(value_definition, str) and value_definition.startswith("$."):
        return resolve_json_path(data, value_definition)

    return value_definition


def extract_metrics(
    event: dict[str, Any],
    definition: dict[str, Any],
) -> list[MetricSample]:
    samples: list[MetricSample] = []

    for metric_def in definition.get("metrics", []):
        labels: dict[str, str] = {}

        for label_name, label_path in metric_def.get("labels", {}).items():
            labels[label_name] = str(resolve_value(event, label_path))

        raw_value = resolve_value(event, metric_def["value"])

        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise MetricExtractionError(
                f"Metric '{metric_def['name']}' value is not numeric: {raw_value}"
            ) from exc

        samples.append(
            MetricSample(
                name=metric_def["name"],
                type=metric_def["type"],
                help=metric_def["help"],
                value=value,
                labels=labels,
            )
        )

    return samples