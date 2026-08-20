import pytest

from app.metrics_engine.metric_yaml_validator import (
    MetricYamlValidationError,
    validate_metric_yaml,
)


@pytest.fixture
def json_schema() -> dict:
    return {
        "type": "object",
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "object",
                "required": [
                    "steps",
                    "duration_seconds",
                    "models",
                    "title",
                ],
                "properties": {
                    "duration_seconds": {"type": "number"},
                    "title": {"type": "string"},
                    "optional_value": {"type": "number"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name", "duration_seconds"],
                            "properties": {
                                "name": {"type": "string"},
                                "duration_seconds": {"type": "number"},
                            },
                        },
                    },
                    "models": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {
                                "name": {"type": "string"},
                            },
                        },
                    },
                },
            }
        },
    }


def test_validate_metric_yaml_with_array_iteration(json_schema: dict) -> None:
    metric_yaml = {
        "version": "1.0",
        "observations": [
            {
                "code": "duration_seconds",
                "value_path": "$.payload.steps[*].duration_seconds",
                "labels": {
                    "step_index": "$index",
                    "step_name": "$.payload.steps[*].name",
                },
            }
        ],
    }

    validated = validate_metric_yaml(
        metric_yaml=metric_yaml,
        json_schema=json_schema,
    )

    observation = validated.observations[0]

    assert validated.version == "1.0"
    assert observation.code == "duration_seconds"
    assert observation.value_path.json_type == "number"
    assert observation.value_path.iterator_path == "$.payload.steps[*]"
    assert observation.labels["step_index"] == "$index"
    assert observation.labels["step_name"].json_type == "string"
    assert observation.labels["step_name"].iterator_path == "$.payload.steps[*]"


@pytest.mark.parametrize(
    ("case_name", "metric_yaml", "expected_message"),
    [
        (
            "unknown field",
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "missing_metric",
                        "value_path": "$.payload.steps[*].missing",
                    }
                ],
            },
            "Property 'missing' does not exist",
        ),
        (
            "non numeric value_path",
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "title_metric",
                        "value_path": "$.payload.title",
                    }
                ],
            },
            "does not support value_path type",
        ),
        (
            "reserved platform label",
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "duration_seconds",
                        "value_path": "$.payload.duration_seconds",
                        "labels": {
                            "ob1_project": "$.payload.title",
                        },
                    }
                ],
            },
            "reserved prefix",
        ),
        (
            "invalid Prometheus label name",
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "duration_seconds",
                        "value_path": "$.payload.duration_seconds",
                        "labels": {
                            "sales-region": "$.payload.title",
                        },
                    }
                ],
            },
            "valid Prometheus label name",
        ),
        (
            "$index without array iteration",
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "duration_seconds",
                        "value_path": "$.payload.duration_seconds",
                        "labels": {
                            "row_index": "$index",
                        },
                    }
                ],
            },
            "uses $index but value_path does not iterate",
        ),
        (
            "label iterates over different array",
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "duration_seconds",
                        "value_path": "$.payload.steps[*].duration_seconds",
                        "labels": {
                            "model": "$.payload.models[*].name",
                        },
                    }
                ],
            },
            "but value_path iterates over",
        ),
    ],
)
def test_reject_invalid_metric_yaml(
    json_schema: dict,
    case_name: str,
    metric_yaml: dict,
    expected_message: str,
) -> None:
    with pytest.raises(MetricYamlValidationError) as exc_info:
        validate_metric_yaml(
            metric_yaml=metric_yaml,
            json_schema=json_schema,
        )

    assert expected_message in str(exc_info.value), case_name


@pytest.mark.parametrize(
    ("metric_yaml", "expected_message"),
    [
        (None, "root must be an object"),
        ({}, "Only metric YAML version '1.0' is supported"),
        (
            {"version": "2.0", "observations": [{}]},
            "Only metric YAML version '1.0' is supported",
        ),
        ({"version": "1.0"}, "must be a non-empty list"),
        ({"version": "1.0", "observations": []}, "must be a non-empty list"),
        (
            {"version": "1.0", "observations": ["metric"]},
            "Each observation must be an object",
        ),
        (
            {"version": "1.0", "observations": [{}]},
            "Observation 'code' is required",
        ),
        (
            {"version": "1.0", "observations": [{"code": ""}]},
            "Observation 'code' is required",
        ),
        (
            {
                "version": "1.0",
                "observations": [{"code": "metric", "transform": ""}],
            },
            "transform must be a non-empty string",
        ),
        (
            {
                "version": "1.0",
                "observations": [
                    {"code": "metric", "transform": "median"}
                ],
            },
            "uses unsupported transform 'median'",
        ),
        (
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "metric",
                        "transform": "constant",
                        "value_path": "$.payload.duration_seconds",
                    }
                ],
            },
            "must not define value_path",
        ),
        (
            {
                "version": "1.0",
                "observations": [{"code": "metric", "transform": "identity"}],
            },
            "must define a non-empty 'value_path'",
        ),
        (
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "metric",
                        "transform": "constant",
                        "labels": [],
                    }
                ],
            },
            "labels must be an object",
        ),
        (
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "metric",
                        "transform": "constant",
                        "labels": {"country": ""},
                    }
                ],
            },
            "must be a non-empty string path",
        ),
        (
            {
                "version": "1.0",
                "observations": [
                    {
                        "code": "metric",
                        "transform": "constant",
                        "labels": {"country": "$.payload.missing"},
                    }
                ],
            },
            "Property 'missing' does not exist",
        ),
    ],
)
def test_reject_invalid_structure_and_rules(
    json_schema: dict,
    metric_yaml,
    expected_message: str,
) -> None:
    with pytest.raises(MetricYamlValidationError, match=expected_message):
        validate_metric_yaml(metric_yaml, json_schema)


def test_default_identity_transform_accepts_optional_numeric_field(
    json_schema: dict,
) -> None:
    validated = validate_metric_yaml(
        {
            "version": "1.0",
            "observations": [
                {
                    "code": "optional_metric",
                    "value_path": "$.payload.optional_value",
                }
            ],
        },
        json_schema,
    )

    observation = validated.observations[0]
    assert observation.transform == "identity"
    assert observation.value_path.required is False
