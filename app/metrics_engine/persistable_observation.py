from __future__ import annotations

from dataclasses import dataclass

from app.metrics_engine.event_scope import EventScope
from app.metrics_engine.observation import Observation


@dataclass(frozen=True)
class PersistableObservation:
    scope: EventScope
    metric_definition_id: int
    metric_definition_version_id: int
    observation: Observation