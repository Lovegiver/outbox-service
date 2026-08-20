from __future__ import annotations

from typing import Any

import yaml
from yaml.constructor import ConstructorError


class MetricYamlParseError(ValueError):
    """Raised when metric YAML cannot be parsed into a safe mapping."""


def parse_metric_yaml(yaml_content: str) -> dict[str, Any]:
    """Parse one metric YAML document with PyYAML's safe loader."""
    if not isinstance(yaml_content, str) or not yaml_content.strip():
        raise MetricYamlParseError("Metric YAML document must not be empty")

    try:
        parsed = yaml.safe_load(yaml_content)
    except ConstructorError as exc:
        raise MetricYamlParseError(
            "Metric YAML contains an unsupported or unsafe YAML construction"
        ) from exc
    except yaml.YAMLError as exc:
        problem = getattr(exc, "problem", None)
        detail = str(problem or "invalid YAML syntax")
        raise MetricYamlParseError(
            f"Invalid metric YAML syntax: {detail}"
        ) from exc

    if parsed is None:
        raise MetricYamlParseError("Metric YAML document must not be empty")

    if not isinstance(parsed, dict):
        raise MetricYamlParseError("Metric YAML root must be an object")

    return parsed
