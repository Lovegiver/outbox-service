from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
import math
import re
from typing import Any

from app.metrics_engine.extractor import MetricSample


PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4"
PROMETHEUS_METRIC_PREFIX = "ob1_"
PROMETHEUS_RESERVED_LABEL_PREFIX = "ob1_"

_METRIC_NAME_INVALID_CHARACTER = re.compile(r"[^a-zA-Z0-9_:]")
_LABEL_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class PrometheusRenderingError(ValueError):
    """Raised when persisted metric state cannot be exposed safely."""


@dataclass(frozen=True)
class PrometheusMetricStateSample:
    """Read-only data required to render one materialized counter series."""

    metric_code: str
    value: float
    business_labels: Mapping[str, Any]
    project_name: str
    event_type_code: str


def normalize_prometheus_metric_name(metric_code: str) -> str:
    """
    Return the Prometheus name for one OB1 business metric.

    Invalid characters are replaced with ``_``. The ``ob1_`` prefix is added
    exactly once, which also guarantees a valid first character.
    """

    normalized = _METRIC_NAME_INVALID_CHARACTER.sub("_", str(metric_code))

    if normalized.startswith(PROMETHEUS_METRIC_PREFIX):
        return normalized

    return f"{PROMETHEUS_METRIC_PREFIX}{normalized}"


def normalize_business_labels(
    labels: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Validate and normalize persisted business dimensions."""

    if labels is None:
        return {}

    if not isinstance(labels, Mapping):
        raise PrometheusRenderingError(
            "Prometheus business labels must be a JSON object."
        )

    normalized: dict[str, str] = {}

    for raw_name, raw_value in labels.items():
        name = validate_prometheus_business_label_name(raw_name)

        if raw_value is None:
            continue

        if isinstance(raw_value, (dict, list)):
            raise PrometheusRenderingError(
                f'Business label "{name}" must contain a scalar value.'
            )

        normalized[name] = str(raw_value)

    return dict(sorted(normalized.items()))


def validate_prometheus_business_label_name(raw_name: object) -> str:
    """Return a valid non-reserved Prometheus business label name."""

    if not isinstance(raw_name, str) or not raw_name:
        raise PrometheusRenderingError(
            "Prometheus business label names must be non-empty strings."
        )

    if raw_name.startswith(PROMETHEUS_RESERVED_LABEL_PREFIX):
        raise PrometheusRenderingError(
            f'Business label "{raw_name}" uses reserved prefix "ob1_".'
        )

    if _LABEL_NAME.fullmatch(raw_name) is None:
        raise PrometheusRenderingError(
            f'Business label "{raw_name}" is not a valid Prometheus label name.'
        )

    return raw_name


def merge_prometheus_labels(
    business_labels: Mapping[str, Any] | None,
    project_name: str,
    event_type_code: str,
) -> dict[str, str]:
    """Merge validated business labels with immutable OB1 platform labels."""

    labels = normalize_business_labels(business_labels)
    labels["ob1_project"] = str(project_name)
    labels["ob1_event_type"] = str(event_type_code)
    return dict(sorted(labels.items()))


def escape_prometheus_label_value(value: str) -> str:
    """Escape a label value according to Prometheus text format 0.0.4."""

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace('"', '\\"')
    )


def render_prometheus_metric_states(
    samples: list[PrometheusMetricStateSample],
) -> str:
    """Render deterministic Prometheus counter families from MetricState."""

    if not samples:
        return ""

    families: defaultdict[
        str,
        list[tuple[tuple[tuple[str, str], ...], float]],
    ] = defaultdict(list)
    source_codes: defaultdict[str, set[str]] = defaultdict(set)
    series_identities: set[tuple[str, tuple[tuple[str, str], ...]]] = set()

    for sample in samples:
        metric_name = normalize_prometheus_metric_name(sample.metric_code)
        source_codes[metric_name].add(sample.metric_code)

        value = float(sample.value)
        if not math.isfinite(value):
            raise PrometheusRenderingError(
                f'Counter "{metric_name}" must contain a finite value.'
            )
        if value < 0:
            raise PrometheusRenderingError(
                f'Counter "{metric_name}" cannot expose a negative value.'
            )

        labels = merge_prometheus_labels(
            business_labels=sample.business_labels,
            project_name=sample.project_name,
            event_type_code=sample.event_type_code,
        )
        label_items = tuple(labels.items())
        identity = (metric_name, label_items)

        if identity in series_identities:
            raise PrometheusRenderingError(
                f'Duplicate Prometheus series detected for "{metric_name}".'
            )

        series_identities.add(identity)
        families[metric_name].append((label_items, value))

    for metric_name, metric_codes in source_codes.items():
        if len(metric_codes) > 1:
            codes = ", ".join(sorted(metric_codes))
            raise PrometheusRenderingError(
                f'Metric codes {codes} normalize to the same Prometheus family '
                f'"{metric_name}".'
            )

    lines: list[str] = []

    for metric_name in sorted(families):
        lines.append(f"# TYPE {metric_name} counter")

        for label_items, value in sorted(families[metric_name]):
            rendered_labels = ",".join(
                f'{name}="{escape_prometheus_label_value(label_value)}"'
                for name, label_value in label_items
            )
            rendered_value = "0" if value == 0 else format(value, ".15g")
            lines.append(f"{metric_name}{{{rendered_labels}}} {rendered_value}")

    return "\n".join(lines) + "\n"


def render_prometheus(samples: list[MetricSample]) -> str:
    """Render legacy in-memory samples while preserving the existing API."""

    lines: list[str] = []
    emitted_headers: set[str] = set()

    for sample in samples:
        if sample.name not in emitted_headers:
            lines.append(f"# HELP {sample.name} {sample.help}")
            lines.append(f"# TYPE {sample.name} {sample.type}")
            emitted_headers.add(sample.name)

        labels = ",".join(
            f'{key}="{escape_prometheus_label_value(value)}"'
            for key, value in sorted(sample.labels.items())
        )

        if labels:
            lines.append(f"{sample.name}{{{labels}}} {sample.value}")
        else:
            lines.append(f"{sample.name} {sample.value}")

    return "\n".join(lines) + "\n"
