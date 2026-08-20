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
