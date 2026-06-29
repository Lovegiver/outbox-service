from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Protocol
from uuid import UUID


class PersistedObject(Protocol):
    id: int


@dataclass(frozen=True)
class PersistedProject:
    id: int
    name: str


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
class PersistedMetricsToken:
    id: int
    project: PersistedProject
    token_prefix: str


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
    json_version_internal: str


@dataclass(frozen=True)
class PersistedRouteDefinition:
    id: int
    event_type: PersistedEventType
    routing_key: str
    destination_name: str


@dataclass(frozen=True)
class PersistedEvent:
    id: int
    project: PersistedProject
    event_type: PersistedEventType
    schema_definition: PersistedSchemaDefinition
    event_uuid: UUID


@dataclass(frozen=True)
class PersistedEventDelivery:
    id: int
    event: PersistedEvent
    destination_name: str


@dataclass(frozen=True)
class PersistedMetricDefinition:
    id: int
    event_type: PersistedEventType
    code: str
    name: str


@dataclass(frozen=True)
class PersistedMetricDefinitionVersion:
    id: int
    metric_definition: PersistedMetricDefinition
    yaml_version_number: int


@dataclass(frozen=True)
class PersistedMetricDefinitionVersionSchema:
    id: int
    metric_definition_version: PersistedMetricDefinitionVersion
    schema_definition: PersistedSchemaDefinition


@dataclass(frozen=True)
class PersistedProcessingChain:
    id: int
    event_type: PersistedEventType
    schema_definition: PersistedSchemaDefinition
    version_number: int


@dataclass(frozen=True)
class PersistedProcessingPlan:
    id: int
    processing_chain: PersistedProcessingChain
    metric_definition: PersistedMetricDefinition
    metric_definition_version: PersistedMetricDefinitionVersion


@dataclass(frozen=True)
class PersistedAnalyticalObservation:
    id: int
    event: PersistedEvent
    metric_code: str


@dataclass(frozen=True)
class PersistedMetricState:
    id: int
    project: PersistedProject
    event_type: PersistedEventType
    metric_code: str
    labels_hash: str


@dataclass(frozen=True)
class PersistedMetricCheckpoint:
    id: int
    checkpoint_name: str


@dataclass(frozen=True)
class PersistedSystemMetric:
    id: int
    metric_code: str
    period_start: datetime
    period_end: datetime
    value: Decimal