from dataclasses import dataclass
from typing import Optional

from tests.domain.persisted_object import (
    PersistedEvent,
    PersistedEventType,
    PersistedMetricDefinition,
    PersistedMetricState,
    PersistedProcessingChain,
    PersistedProject,
    PersistedUserAccount,
)


@dataclass(frozen=True)
class ProjectRecord:
    name: str
    description: Optional[str] = None
    is_active: bool = True


@dataclass(frozen=True)
class UserAccountRecord:
    email: str
    password_hash: str = "test-password-hash"
    is_active: bool = True
    is_admin: bool = False


@dataclass(frozen=True)
class ProjectMemberRecord:
    project: PersistedProject
    user: PersistedUserAccount
    role: str


@dataclass(frozen=True)
class ApiKeyRecord:
    project: PersistedProject
    name: str
    key_prefix: str = "test"
    key_hash: str = "test-key-hash"
    is_active: bool = True


@dataclass(frozen=True)
class EventTypeRecord:
    project: PersistedProject
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool = True


@dataclass(frozen=True)
class SchemaDefinitionRecord:
    event_type: PersistedEventType
    version: int
    json_schema: dict
    is_active: bool = True


@dataclass(frozen=True)
class RouteDefinitionRecord:
    event_type: PersistedEventType
    name: str
    target_url: str = "https://example.test/webhook"
    method: str = "POST"
    is_active: bool = True


@dataclass(frozen=True)
class EventRecord:
    event_type: PersistedEventType
    payload: dict
    event_uuid: str
    status: str = "RECEIVED"


@dataclass(frozen=True)
class MetricDefinitionRecord:
    event_type: PersistedEventType
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool = True


@dataclass(frozen=True)
class MetricDefinitionVersionRecord:
    metric_definition: PersistedMetricDefinition
    version: int
    yaml_definition: dict
    is_active: bool = True


@dataclass(frozen=True)
class ProcessingChainRecord:
    event_type: PersistedEventType
    status: str = "ACTIVE"


@dataclass(frozen=True)
class ProcessingPlanRecord:
    processing_chain: PersistedProcessingChain
    compiled_plan_json: Optional[dict] = None


@dataclass(frozen=True)
class AnalyticalObservationRecord:
    event: Optional[PersistedEvent]
    metric_code: str
    value: float
    labels: Optional[dict] = None


@dataclass(frozen=True)
class MetricStateRecord:
    metric_definition: PersistedMetricDefinition
    value: float = 0.0


@dataclass(frozen=True)
class MetricCheckpointRecord:
    metric_state: PersistedMetricState
    checkpoint_value: float = 0.0