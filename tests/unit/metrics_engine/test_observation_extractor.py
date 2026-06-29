import pytest

from app.metrics_engine.metric_yaml_validator import validate_metric_yaml
from app.metrics_engine.observation import Observation
from app.metrics_engine.observation_extractor import (
    ExtractionLimits,
    ObservationExtractionError,
    extract_observations,
)


def test_extract_single_numeric_observation() -> None:
    json_schema = {
        "type": "object",
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "object",
                "required": ["duration_seconds"],
                "properties": {
                    "duration_seconds": {"type": "number"},
                },
            }
        },
    }

    metric_yaml = {
        "version": "1.0",
        "observations": [
            {
                "code": "duration_seconds",
                "value_path": "$.payload.duration_seconds",
            }
        ],
    }

    payload = {
        "payload": {
            "duration_seconds": 42,
        }
    }

    validated_yaml = validate_metric_yaml(
        metric_yaml=metric_yaml,
        json_schema=json_schema,
    )

    observations = extract_observations(
        payload=payload,
        metric_yaml=validated_yaml,
    )

    assert len(observations) == 1

    observation = observations[0]

    assert observation.metric_code == "duration_seconds"
    assert observation.value == 42.0
    assert observation.dimensions == {}

def test_extract_array_observations_with_dimensions() -> None:
    json_schema = {
        "type": "object",
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "object",
                "required": ["steps"],
                "properties": {
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
                    }
                },
            }
        },
    }

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

    payload = {
        "payload": {
            "steps": [
                {
                    "name": "extract",
                    "duration_seconds": 28,
                },
                {
                    "name": "validate",
                    "duration_seconds": 32,
                },
                {
                    "name": "persist",
                    "duration_seconds": 16,
                },
            ]
        }
    }

    validated_yaml = validate_metric_yaml(
        metric_yaml=metric_yaml,
        json_schema=json_schema,
    )

    observations = extract_observations(
        payload=payload,
        metric_yaml=validated_yaml,
    )

    assert observations == [
        Observation(
            metric_code="duration_seconds",
            value=28.0,
            dimensions={
                "step_index": 0,
                "step_name": "extract",
            },
        ),
        Observation(
            metric_code="duration_seconds",
            value=32.0,
            dimensions={
                "step_index": 1,
                "step_name": "validate",
            },
        ),
        Observation(
            metric_code="duration_seconds",
            value=16.0,
            dimensions={
                "step_index": 2,
                "step_name": "persist",
            },
        ),
    ]

def test_reject_when_matches_exceed_observation_limit() -> None:
    json_schema = {
        "type": "object",
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "object",
                "required": ["values"],
                "properties": {
                    "values": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["duration_seconds"],
                            "properties": {
                                "duration_seconds": {"type": "number"},
                            },
                        },
                    }
                },
            }
        },
    }

    metric_yaml = {
        "version": "1.0",
        "observations": [
            {
                "code": "duration_seconds",
                "value_path": "$.payload.values[*].duration_seconds",
            }
        ],
    }

    payload = {
        "payload": {
            "values": [
                {"duration_seconds": 1},
                {"duration_seconds": 2},
                {"duration_seconds": 3},
            ]
        }
    }

    validated_yaml = validate_metric_yaml(
        metric_yaml=metric_yaml,
        json_schema=json_schema,
    )

    with pytest.raises(ObservationExtractionError) as exc_info:
        extract_observations(
            payload=payload,
            metric_yaml=validated_yaml,
            limits=ExtractionLimits(max_matches_per_observation=2),
        )

    assert "exceeding limit 2" in str(exc_info.value)


def test_reject_when_event_observation_limit_is_exceeded() -> None:
    json_schema = {
        "type": "object",
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "object",
                "required": ["first", "second"],
                "properties": {
                    "first": {"type": "number"},
                    "second": {"type": "number"},
                },
            }
        },
    }

    metric_yaml = {
        "version": "1.0",
        "observations": [
            {
                "code": "first",
                "value_path": "$.payload.first",
            },
            {
                "code": "second",
                "value_path": "$.payload.second",
            },
        ],
    }

    payload = {
        "payload": {
            "first": 1,
            "second": 2,
        }
    }

    validated_yaml = validate_metric_yaml(
        metric_yaml=metric_yaml,
        json_schema=json_schema,
    )

    with pytest.raises(ObservationExtractionError) as exc_info:
        extract_observations(
            payload=payload,
            metric_yaml=validated_yaml,
            limits=ExtractionLimits(max_observations_per_event=1),
        )

    assert "more than 1 observations" in str(exc_info.value)