from dataclasses import dataclass
from typing import Optional, Protocol


class PersistedObject(Protocol):
    id: int


@dataclass(frozen=True)
class PersistedProject:
    id: int
    name: str


@dataclass(frozen=True)
class PersistedEventType:
    id: int
    project: PersistedProject
    code: str
    name: str


@dataclass(frozen=True)
class PersistedSchemaDefinition:
    id: int
    event_type: PersistedEventType
    version: int


@dataclass(frozen=True)
class PersistedUserAccount:
    id: int
    email: str


@dataclass(frozen=True)
class PersistedProjectMember:
    id: int
    project: PersistedProject
    user: PersistedUserAccount
    role: str


@dataclass(frozen=True)
class PersistedApiKey:
    id: int
    project: PersistedProject
    key_prefix: str


@dataclass(frozen=True)
class PersistedRouteDefinition:
    id: int
    event_type: PersistedEventType
    name: str


@dataclass(frozen=True)
class PersistedEvent:
    id: int
    event_type: PersistedEventType
    event_uuid: str


@dataclass(frozen=True)
class PersistedMetricDefinition:
    id: int
    event_type: PersistedEventType
    code: str


@dataclass(frozen=True)
class PersistedMetricDefinitionVersion:
    id: int
    metric_definition: PersistedMetricDefinition
    version: int


@dataclass(frozen=True)
class PersistedProcessingChain:
    id: int
    event_type: PersistedEventType


@dataclass(frozen=True)
class PersistedProcessingPlan:
    id: int
    processing_chain: PersistedProcessingChain


@dataclass(frozen=True)
class PersistedAnalyticalObservation:
    id: int
    event: Optional[PersistedEvent]
    metric_code: str


@dataclass(frozen=True)
class PersistedMetricState:
    id: int
    metric_definition: PersistedMetricDefinition


@dataclass(frozen=True)
class PersistedMetricCheckpoint:
    id: int
    metric_state: PersistedMetricState