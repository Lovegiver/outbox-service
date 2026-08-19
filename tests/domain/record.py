from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from tests.domain.persisted_object import (
    PersistedEvent,
    PersistedEventType,
    PersistedMetricDefinition,
    PersistedMetricDefinitionVersion,
    PersistedMetricState,
    PersistedProcessingChain,
    PersistedProject,
    PersistedSchemaDefinition,
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
    role: str = "USER"
    is_active: bool = True


@dataclass(frozen=True)
class ProjectMemberRecord:
    project: PersistedProject
    user: PersistedUserAccount
    role: str = "VIEWER"


@dataclass(frozen=True)
class ApiKeyRecord:
    project: PersistedProject
    name: str = "test-api-key"
    key_prefix: str = "test"
    key_hash: Optional[str] = None
    is_active: bool = True


@dataclass(frozen=True)
class MetricsTokenRecord:
    project: PersistedProject
    event_type: Optional[PersistedEventType] = None
    name: str = "test-metrics-token"
    token_prefix: str = "test"
    token_hash: Optional[str] = None
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
    json_schema: dict = field(default_factory=lambda: {"type": "object"})
    json_version_internal: str = "1.0"
    json_version_client: Optional[str] = None
    is_active: bool = True


@dataclass(frozen=True)
class RouteDefinitionRecord:
    event_type: PersistedEventType
    routing_key: str
    destination_name: str = "test-destination"
    destination_url: str = "https://example.test/webhook"
    is_active: bool = True
    auth_type: str = "NONE"
    auth_config: Optional[dict] = None
    secret_ref: Optional[str] = None


@dataclass(frozen=True)
class EventRecord:
    event_type: PersistedEventType
    schema_definition: PersistedSchemaDefinition
    payload: dict = field(default_factory=dict)
    event_uuid: UUID = field(default_factory=uuid4)
    correlation_id: Optional[str] = None
    json_version_internal: str = "1.0"
    status: str = "RECEIVED"


@dataclass(frozen=True)
class EventDeliveryRecord:
    event: PersistedEvent
    destination_name: str = "test-destination"
    destination_type: str = "HTTP"
    destination_url: Optional[str] = "https://example.test/webhook"
    auth_type: str = "NONE"
    auth_config: Optional[dict] = None
    secret_ref: Optional[str] = None
    status: str = "PENDING"
    attempt_count: int = 0
    last_error: Optional[str] = None
    next_attempt_at: Optional[datetime] = None


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
    yaml_version_number: int = 1
    yaml_version_label: Optional[str] = None
    yaml_content: str = "version: '1.0'\nobservations: []\n"
    is_active: bool = True


@dataclass(frozen=True)
class MetricDefinitionVersionSchemaRecord:
    metric_definition_version: PersistedMetricDefinitionVersion
    schema_definition: PersistedSchemaDefinition


@dataclass(frozen=True)
class ProcessingChainRecord:
    event_type: PersistedEventType
    schema_definition: PersistedSchemaDefinition
    version_number: int = 1
    status: str = "DRAFT"
    is_active: bool = False


@dataclass(frozen=True)
class ProcessingPlanRecord:
    processing_chain: PersistedProcessingChain
    metric_definition: PersistedMetricDefinition
    metric_definition_version: PersistedMetricDefinitionVersion
    position: int = 0
    is_active: bool = True
    compiled_plan_json: Optional[dict] = None


@dataclass(frozen=True)
class AnalyticalObservationRecord:
    event: PersistedEvent
    metric_definition: PersistedMetricDefinition
    metric_definition_version: PersistedMetricDefinitionVersion
    metric_code: str
    value: float
    dimensions_json: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MetricStateRecord:
    project: PersistedProject
    event_type: PersistedEventType
    metric_code: str
    labels_json: dict = field(default_factory=dict)
    labels_hash: Optional[str] = None
    value: float = 0.0
    metric_definition: Optional[PersistedMetricDefinition] = None
    metric_definition_version: Optional[PersistedMetricDefinitionVersion] = None


@dataclass(frozen=True)
class MetricCheckpointRecord:
    checkpoint_name: str = "default"
    last_processed_observation_id: int = 0


@dataclass(frozen=True)
class SystemMetricRecord:
    metric_code: str
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    value: Decimal = Decimal("0")
    project: Optional[PersistedProject] = None
    event_type: Optional[PersistedEventType] = None
