from __future__ import annotations

from dataclasses import dataclass

DimensionValue = str | int | float | bool | None


@dataclass(frozen=True)
class Observation:
    metric_code: str
    value: float
    dimensions: dict[str, DimensionValue]
