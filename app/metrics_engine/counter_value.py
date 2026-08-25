from __future__ import annotations

import math
from numbers import Real
from typing import Iterable


class CounterValueError(ValueError):
    """Raised when a value cannot be used as a Counter increment."""

    def __init__(self, code: str, context: str) -> None:
        self.code = code
        super().__init__(f"{code}: {context}")


def normalize_counter_increment(value: object, *, context: str) -> float:
    """Return one finite, non-negative Counter increment."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise CounterValueError(
            "COUNTER_VALUE_NOT_NUMERIC",
            f"{context} must produce a numeric Counter increment",
        )

    normalized = float(value)
    if not math.isfinite(normalized):
        raise CounterValueError(
            "COUNTER_VALUE_NOT_FINITE",
            f"{context} must produce a finite Counter increment",
        )
    if normalized < 0:
        raise CounterValueError(
            "COUNTER_VALUE_NEGATIVE",
            f"{context} must produce a non-negative Counter increment",
        )

    return 0.0 if normalized == 0 else normalized


def coalesce_counter_increments(
    values: Iterable[object],
    *,
    context: str,
) -> float:
    """Add validated Counter increments and reject a non-finite total."""
    normalized = [
        normalize_counter_increment(value, context=context) for value in values
    ]
    try:
        total = math.fsum(sorted(normalized))
    except OverflowError as exc:
        raise CounterValueError(
            "COUNTER_VALUE_NOT_FINITE",
            f"{context} produces a non-finite Counter total",
        ) from exc
    return normalize_counter_increment(total, context=context)
