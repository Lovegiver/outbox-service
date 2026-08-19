from __future__ import annotations

import hashlib
import json

from datetime import datetime, timezone
from psycopg.types.json import Jsonb
from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.domain.persisted_object import *
from tests.domain.record import *


class ObjectFactory:
    def __init__(self, connection: Connection):
        self.connection = connection

    def _insert(self, table: str, values: dict) -> int:
        columns = ", ".join(values.keys())
        params = ", ".join(f":{key}" for key in values.keys())

        result = self.connection.execute(
            text(
                f"""
                INSERT INTO outbox.{table} ({columns})
                VALUES ({params})
                RETURNING id
                """
            ),
            values,
        )

        return int(result.scalar_one())

    @staticmethod
    def _hash_labels(labels: dict) -> str:
        payload = json.dumps(labels, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def project(self, record: ProjectRecord) -> PersistedProject:
        object_id = self._insert(
            "project",
            {
                "name": record.name,
                "description": record.description,
                "is_active": record.is_active,
            },
        )
        return PersistedProject(id=object_id, name=record.name)

    def user_account(self, record: UserAccountRecord) -> PersistedUserAccount:
        object_id = self._insert(
            "user_account",
            {
                "email": record.email,
                "password_hash": record.password_hash,
                "role": record.role,
                "is_active": record.is_active,
            },
        )
        return PersistedUserAccount(id=object_id, email=record.email)

    def project_member(self, record: ProjectMemberRecord) -> PersistedProjectMember:
        object_id = self._insert(
            "project_member",
            {
                "project_id": record.project.id,
                "user_id": record.user.id,
                "role": record.role,
            },
        )
        return PersistedProjectMember(
            id=object_id,
            project=record.project,
            user=record.user,
            role=record.role,
        )

    def api_key(self, record: ApiKeyRecord) -> PersistedApiKey:
        key_hash = record.key_hash or f"{record.key_prefix}-hash"

        object_id = self._insert(
            "api_key",
            {
                "project_id": record.project.id,
                "name": record.name,
                "key_prefix": record.key_prefix,
                "key_hash": key_hash,
                "is_active": record.is_active,
            },
        )
        return PersistedApiKey(
            id=object_id,
            project=record.project,
            key_prefix=record.key_prefix,
        )

    def metrics_token(self, record: MetricsTokenRecord) -> PersistedMetricsToken:
        token_hash = record.token_hash or f"{record.token_prefix}-hash"

        object_id = self._insert(
            "metrics_token",
            {
                "project_id": record.project.id,
                "event_type_id": record.event_type.id if record.event_type else None,
                "name": record.name,
                "token_prefix": record.token_prefix,
                "token_hash": token_hash,
                "is_active": record.is_active,
            },
        )
        return PersistedMetricsToken(
            id=object_id,
            project=record.project,
            token_prefix=record.token_prefix,
        )

    def event_type(self, record: EventTypeRecord) -> PersistedEventType:
        object_id = self._insert(
            "event_type",
            {
                "project_id": record.project.id,
                "code": record.code,
                "name": record.name,
                "description": record.description,
                "is_active": record.is_active,
            },
        )
        return PersistedEventType(
            id=object_id,
            project=record.project,
            code=record.code,
            name=record.name,
        )

    def schema_definition(self, record: SchemaDefinitionRecord) -> PersistedSchemaDefinition:
        object_id = self._insert(
            "schema_definition",
            {
                "event_type_id": record.event_type.id,
                "json_version_client": record.json_version_client,
                "json_version_internal": record.json_version_internal,
                "json_schema": Jsonb(record.json_schema),
                "is_active": record.is_active,
            },
        )
        return PersistedSchemaDefinition(
            id=object_id,
            event_type=record.event_type,
            json_version_internal=record.json_version_internal,
        )

    def route_definition(self, record: RouteDefinitionRecord) -> PersistedRouteDefinition:
        object_id = self._insert(
            "route_definition",
            {
                "event_type_id": record.event_type.id,
                "routing_key": record.routing_key,
                "destination_name": record.destination_name,
                "destination_url": record.destination_url,
                "is_active": record.is_active,
                "auth_type": record.auth_type,
                "auth_config": Jsonb(record.auth_config) if record.auth_config is not None else None,
                "secret_ref": record.secret_ref,
            },
        )
        return PersistedRouteDefinition(
            id=object_id,
            event_type=record.event_type,
            routing_key=record.routing_key,
            destination_name=record.destination_name,
        )

    def event(self, record: EventRecord) -> PersistedEvent:
        object_id = self._insert(
            "event",
            {
                "event_uuid": record.event_uuid,
                "correlation_id": record.correlation_id,
                "project_id": record.event_type.project.id,
                "event_type_id": record.event_type.id,
                "json_version_internal": record.json_version_internal,
                "schema_definition_id": record.schema_definition.id,
                "payload": Jsonb(record.payload),
                "status": record.status,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        return PersistedEvent(
            id=object_id,
            project=record.event_type.project,
            event_type=record.event_type,
            schema_definition=record.schema_definition,
            event_uuid=record.event_uuid,
        )

    def event_delivery(self, record: EventDeliveryRecord) -> PersistedEventDelivery:
        object_id = self._insert(
            "event_delivery",
            {
                "event_id": record.event.id,
                "destination_name": record.destination_name,
                "destination_type": record.destination_type,
                "destination_url": record.destination_url,
                "auth_type": record.auth_type,
                "auth_config": Jsonb(record.auth_config) if record.auth_config is not None else None,
                "secret_ref": record.secret_ref,
                "status": record.status,
                "attempt_count": record.attempt_count,
                "last_error": record.last_error,
                "next_attempt_at": record.next_attempt_at,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )
        return PersistedEventDelivery(
            id=object_id,
            event=record.event,
            destination_name=record.destination_name,
        )

    def metric_definition(self, record: MetricDefinitionRecord) -> PersistedMetricDefinition:
        object_id = self._insert(
            "metric_definition",
            {
                "event_type_id": record.event_type.id,
                "code": record.code,
                "name": record.name,
                "description": record.description,
                "is_active": record.is_active,
            },
        )
        return PersistedMetricDefinition(
            id=object_id,
            event_type=record.event_type,
            code=record.code,
            name=record.name,
        )

    def metric_definition_version(
        self,
        record: MetricDefinitionVersionRecord,
    ) -> PersistedMetricDefinitionVersion:
        object_id = self._insert(
            "metric_definition_version",
            {
                "metric_definition_id": record.metric_definition.id,
                "yaml_version_number": record.yaml_version_number,
                "yaml_version_label": record.yaml_version_label,
                "yaml_content": record.yaml_content,
                "is_active": record.is_active,
            },
        )
        return PersistedMetricDefinitionVersion(
            id=object_id,
            metric_definition=record.metric_definition,
            yaml_version_number=record.yaml_version_number,
        )

    def metric_definition_version_schema(
        self,
        record: MetricDefinitionVersionSchemaRecord,
    ) -> PersistedMetricDefinitionVersionSchema:
        object_id = self._insert(
            "metric_definition_version_schema",
            {
                "metric_definition_version_id": record.metric_definition_version.id,
                "schema_definition_id": record.schema_definition.id,
            },
        )
        return PersistedMetricDefinitionVersionSchema(
            id=object_id,
            metric_definition_version=record.metric_definition_version,
            schema_definition=record.schema_definition,
        )

    def processing_chain(self, record: ProcessingChainRecord) -> PersistedProcessingChain:
        object_id = self._insert(
            "processing_chain",
            {
                "event_type_id": record.event_type.id,
                "schema_definition_id": record.schema_definition.id,
                "version_number": record.version_number,
                "status": record.status,
                "is_active": record.is_active,
            },
        )
        return PersistedProcessingChain(
            id=object_id,
            event_type=record.event_type,
            schema_definition=record.schema_definition,
            version_number=record.version_number,
        )

    def processing_plan(self, record: ProcessingPlanRecord) -> PersistedProcessingPlan:
        object_id = self._insert(
            "processing_plan",
            {
                "processing_chain_id": record.processing_chain.id,
                "metric_definition_id": record.metric_definition.id,
                "metric_definition_version_id": record.metric_definition_version.id,
                "position": record.position,
                "is_active": record.is_active,
                "compiled_plan_json": Jsonb(record.compiled_plan_json) if record.compiled_plan_json is not None else None,
            },
        )
        return PersistedProcessingPlan(
            id=object_id,
            processing_chain=record.processing_chain,
            metric_definition=record.metric_definition,
            metric_definition_version=record.metric_definition_version,
        )

    def analytical_observation(
        self,
        record: AnalyticalObservationRecord,
    ) -> PersistedAnalyticalObservation:
        object_id = self._insert(
            "analytical_observation",
            {
                "project_id": record.event.project.id,
                "event_type_id": record.event.event_type.id,
                "event_id": record.event.id,
                "metric_definition_id": record.metric_definition.id,
                "metric_definition_version_id": record.metric_definition_version.id,
                "metric_code": record.metric_code,
                "value": record.value,
                "dimensions_json": Jsonb(record.dimensions_json),
            },
        )
        return PersistedAnalyticalObservation(
            id=object_id,
            event=record.event,
            metric_code=record.metric_code,
        )

    def metric_state(self, record: MetricStateRecord) -> PersistedMetricState:
        labels_hash = record.labels_hash or self._hash_labels(record.labels_json)

        object_id = self._insert(
            "metric_state",
            {
                "project_id": record.project.id,
                "event_type_id": record.event_type.id,
                "metric_definition_id": record.metric_definition.id if record.metric_definition else None,
                "metric_definition_version_id": (
                    record.metric_definition_version.id
                    if record.metric_definition_version
                    else None
                ),
                "metric_code": record.metric_code,
                "labels_hash": labels_hash,
                "labels_json": Jsonb(record.labels_json),
                "value": record.value,
            },
        )
        return PersistedMetricState(
            id=object_id,
            project=record.project,
            event_type=record.event_type,
            metric_code=record.metric_code,
            labels_hash=labels_hash,
        )

    def metric_checkpoint(self, record: MetricCheckpointRecord) -> PersistedMetricCheckpoint:
        object_id = self._insert(
            "metric_checkpoint",
            {
                "checkpoint_name": record.checkpoint_name,
                "last_processed_observation_id": record.last_processed_observation_id,
            },
        )
        return PersistedMetricCheckpoint(
            id=object_id,
            checkpoint_name=record.checkpoint_name,
        )

    def system_metric(self, record: SystemMetricRecord) -> PersistedSystemMetric:
        object_id = self._insert(
            "system_metric",
            {
                "metric_code": record.metric_code,
                "project_id": record.project.id if record.project else None,
                "event_type_id": record.event_type.id if record.event_type else None,
                "period_start": record.period_start,
                "period_end": record.period_end,
                "value": record.value,
            },
        )
        return PersistedSystemMetric(
            id=object_id,
            metric_code=record.metric_code,
            period_start=record.period_start,
            period_end=record.period_end,
            value=record.value,
        )
