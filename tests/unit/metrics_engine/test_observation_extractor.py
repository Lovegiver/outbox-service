from copy import deepcopy

import pytest

from app.metrics_engine.counter_value import CounterValueError
from app.metrics_engine.metric_yaml_validator import validate_metric_yaml
from app.metrics_engine.observation import Observation
from app.metrics_engine.observation_extractor import (
    ExtractionLimits,
    ObservationExtractionError,
    extract_keyed_observations_from_compiled_plan,
    extract_observations,
)


def compiled_observation(
    *,
    transform: str,
    path: str = "",
    required: bool = True,
    json_type: str = "constant",
    labels: list[dict] | None = None,
) -> dict:
    return {
        "compiler_version": "1.0",
        "yaml_version": "1.0",
        "observations": [
            {
                "metric_code": "runtime_total",
                "transform": transform,
                "value": {
                    "path": path,
                    "json_type": json_type,
                    "required": required,
                    "iterator_path": None,
                },
                "labels": labels or [],
            }
        ],
    }


@pytest.mark.parametrize(
    ("transform", "path", "payload", "expected"),
    [
        ("constant", "", {}, 1.0),
        ("identity", "$.amount", {"amount": 2.5}, 2.5),
        ("count", "$.items", {"items": [1, 2, 3]}, 3.0),
        ("length", "$.name", {"name": "abc"}, 3.0),
        ("to_number", "$.active", {"active": True}, 1.0),
    ],
)
def test_compiled_runtime_executes_every_activable_transform(
    transform: str,
    path: str,
    payload: dict,
    expected: float,
) -> None:
    result = extract_keyed_observations_from_compiled_plan(
        payload,
        compiled_observation(transform=transform, path=path),
    )

    assert result[0].observation.value == expected
    assert result[0].observation_key == "observation:0:occurrence:0"


@pytest.mark.parametrize(
    ("value", "error_code"),
    [
        (-1, "COUNTER_VALUE_NEGATIVE"),
        (-0.5, "COUNTER_VALUE_NEGATIVE"),
        (float("nan"), "COUNTER_VALUE_NOT_FINITE"),
        (float("inf"), "COUNTER_VALUE_NOT_FINITE"),
        (float("-inf"), "COUNTER_VALUE_NOT_FINITE"),
        ("3", "COUNTER_VALUE_NOT_NUMERIC"),
        (True, "COUNTER_VALUE_NOT_NUMERIC"),
    ],
)
def test_identity_rejects_invalid_counter_before_creating_observation(
    value: object,
    error_code: str,
) -> None:
    plan = compiled_observation(
        transform="identity",
        path="$.amount",
        json_type="number",
    )
    original_plan = deepcopy(plan)

    with pytest.raises(CounterValueError) as exc_info:
        extract_keyed_observations_from_compiled_plan({"amount": value}, plan)

    assert exc_info.value.code == error_code
    assert plan == original_plan


def test_identity_normalizes_negative_zero_and_to_number_accepts_boolean() -> None:
    identity = extract_keyed_observations_from_compiled_plan(
        {"amount": -0.0},
        compiled_observation(transform="identity", path="$.amount"),
    )
    converted = extract_keyed_observations_from_compiled_plan(
        {"active": False},
        compiled_observation(transform="to_number", path="$.active"),
    )

    assert identity[0].observation.value == 0.0
    assert converted[0].observation.value == 0.0


def test_optional_missing_value_skips_only_its_observation() -> None:
    result = extract_keyed_observations_from_compiled_plan(
        {},
        compiled_observation(
            transform="identity",
            path="$.optional_amount",
            required=False,
            json_type="number",
        ),
    )

    assert result == []


def test_optional_missing_label_is_structurally_null() -> None:
    result = extract_keyed_observations_from_compiled_plan(
        {},
        compiled_observation(
            transform="constant",
            labels=[
                {
                    "name": "country",
                    "kind": "path",
                    "path": "$.country",
                    "json_type": "string",
                    "required": False,
                    "iterator_path": None,
                }
            ],
        ),
    )

    assert result[0].observation.dimensions == {"country": None}


def test_literal_missing_value_is_an_ordinary_business_label() -> None:
    result = extract_keyed_observations_from_compiled_plan(
        {"country": "__missing__"},
        compiled_observation(
            transform="constant",
            labels=[
                {
                    "name": "country",
                    "kind": "path",
                    "path": "$.country",
                    "json_type": "string",
                    "required": False,
                    "iterator_path": None,
                }
            ],
        ),
    )

    assert result[0].observation.dimensions == {"country": "__missing__"}


def test_compiled_runtime_rejects_unknown_operation_and_incomplete_document() -> None:
    with pytest.raises(ObservationExtractionError, match="unsupported runtime"):
        extract_keyed_observations_from_compiled_plan(
            {"value": 1},
            compiled_observation(transform="unknown", path="$.value"),
        )

    with pytest.raises(ObservationExtractionError, match="compiler version"):
        extract_keyed_observations_from_compiled_plan({}, {"observations": []})


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
