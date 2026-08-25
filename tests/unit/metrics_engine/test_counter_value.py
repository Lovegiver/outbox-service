import math

import pytest

from app.metrics_engine.counter_value import (
    CounterValueError,
    coalesce_counter_increments,
    normalize_counter_increment,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, 1.0), (2.5, 2.5), (0, 0.0), (-0.0, 0.0)],
)
def test_accept_counter_increment_boundaries(value: object, expected: float) -> None:
    result = normalize_counter_increment(value, context="runtime observation")

    assert result == expected
    if expected == 0:
        assert math.copysign(1, result) == 1


@pytest.mark.parametrize("value", [-1, -0.5])
def test_reject_negative_counter_increment_with_stable_code(value: object) -> None:
    with pytest.raises(CounterValueError) as exc_info:
        normalize_counter_increment(value, context="runtime observation")

    assert exc_info.value.code == "COUNTER_VALUE_NEGATIVE"


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_reject_non_finite_counter_increment_with_stable_code(value: float) -> None:
    with pytest.raises(CounterValueError) as exc_info:
        normalize_counter_increment(value, context="runtime observation")

    assert exc_info.value.code == "COUNTER_VALUE_NOT_FINITE"


@pytest.mark.parametrize("value", ["3", True, False, None])
def test_reject_non_numeric_counter_increment_with_stable_code(value: object) -> None:
    with pytest.raises(CounterValueError) as exc_info:
        normalize_counter_increment(value, context="runtime observation")

    assert exc_info.value.code == "COUNTER_VALUE_NOT_NUMERIC"


def test_reject_non_finite_coalesced_counter_total() -> None:
    with pytest.raises(CounterValueError) as exc_info:
        coalesce_counter_increments(
            [1e308, 1e308],
            context="coalesced counter",
        )

    assert exc_info.value.code == "COUNTER_VALUE_NOT_FINITE"
