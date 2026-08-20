import pytest

from app.metrics_engine.metric_yaml_parser import (
    MetricYamlParseError,
    parse_metric_yaml,
)


def test_parse_valid_yaml_and_preserve_scalar_meaning() -> None:
    parsed = parse_metric_yaml(
        """version: "1.0"
observations:
  - code: products_sold_total
    transform: constant
    labels:
      country_code: "001"
      enabled: true
"""
    )

    assert parsed["version"] == "1.0"
    labels = parsed["observations"][0]["labels"]
    assert labels == {"country_code": "001", "enabled": True}


def test_reject_invalid_syntax_with_a_deterministic_error() -> None:
    invalid_yaml = 'version: ["1.0"'

    with pytest.raises(MetricYamlParseError) as first_error:
        parse_metric_yaml(invalid_yaml)
    with pytest.raises(MetricYamlParseError) as second_error:
        parse_metric_yaml(invalid_yaml)

    assert str(first_error.value) == str(second_error.value)
    assert str(first_error.value).startswith("Invalid metric YAML syntax:")


@pytest.mark.parametrize("yaml_content", ["", "   ", "# comment only\n"])
def test_reject_empty_document(yaml_content: str) -> None:
    with pytest.raises(
        MetricYamlParseError,
        match="Metric YAML document must not be empty",
    ):
        parse_metric_yaml(yaml_content)


@pytest.mark.parametrize("yaml_content", ["- version\n- observations\n", "42\n"])
def test_reject_non_object_root(yaml_content: str) -> None:
    with pytest.raises(
        MetricYamlParseError,
        match="Metric YAML root must be an object",
    ):
        parse_metric_yaml(yaml_content)


def test_reject_unsafe_yaml_construction() -> None:
    with pytest.raises(
        MetricYamlParseError,
        match="unsupported or unsafe YAML construction",
    ):
        parse_metric_yaml(
            "!!python/object/apply:builtins.eval ['2 + 2']"
        )
