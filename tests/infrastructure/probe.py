from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.domain.persisted_object import PersistedObject


class BaseProbe:
    def __init__(self, connection: Connection, table_name: str):
        self.connection = connection
        self.table_name = table_name

    def exists(self, persisted: PersistedObject) -> bool:
        return self.exists_by_id(persisted.id)

    def exists_by_id(self, object_id: int) -> bool:
        return self.exists_where("id = :id", {"id": object_id})

    def count(self) -> int:
        result = self.connection.execute(
            text(f"SELECT COUNT(*) FROM outbox.{self.table_name}")
        )
        return int(result.scalar_one())

    def exists_where(self, where_clause: str, params: dict[str, Any]) -> bool:
        result = self.connection.execute(
            text(
                f"""
                SELECT EXISTS (
                    SELECT 1
                    FROM outbox.{self.table_name}
                    WHERE {where_clause}
                )
                """
            ),
            params,
        )
        return bool(result.scalar_one())


class Probe:
    def __init__(self, connection: Connection):
        self.project = ProjectProbe(connection)
        self.user_account = UserAccountProbe(connection)
        self.project_member = ProjectMemberProbe(connection)
        self.api_key = ApiKeyProbe(connection)
        self.metrics_token = MetricsTokenProbe(connection)
        self.event_type = EventTypeProbe(connection)
        self.schema_definition = SchemaDefinitionProbe(connection)
        self.route_definition = RouteDefinitionProbe(connection)
        self.event = EventProbe(connection)
        self.event_delivery = EventDeliveryProbe(connection)
        self.metric_definition = MetricDefinitionProbe(connection)
        self.metric_definition_version = MetricDefinitionVersionProbe(connection)
        self.metric_definition_version_schema = MetricDefinitionVersionSchemaProbe(connection)
        self.processing_chain = ProcessingChainProbe(connection)
        self.processing_plan = ProcessingPlanProbe(connection)
        self.analytical_observation = AnalyticalObservationProbe(connection)
        self.metric_state = MetricStateProbe(connection)
        self.metric_checkpoint = MetricCheckpointProbe(connection)
        self.system_metric = SystemMetricProbe(connection)


class ProjectProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "project")

    def exists_by_name(self, name: str) -> bool:
        return self.exists_where("name = :name", {"name": name})


class UserAccountProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "user_account")

    def exists_by_email(self, email: str) -> bool:
        return self.exists_where("email = :email", {"email": email})


class ProjectMemberProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "project_member")

    def exists_by_project_and_user(self, project: PersistedObject, user: PersistedObject) -> bool:
        return self.exists_where(
            "project_id = :project_id AND user_id = :user_id",
            {"project_id": project.id, "user_id": user.id},
        )


class ApiKeyProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "api_key")

    def exists_by_key_prefix(self, key_prefix: str) -> bool:
        return self.exists_where("key_prefix = :key_prefix", {"key_prefix": key_prefix})

    def exists_active_by_key_prefix(self, key_prefix: str) -> bool:
        return self.exists_where(
            "key_prefix = :key_prefix AND is_active = true",
            {"key_prefix": key_prefix},
        )


class MetricsTokenProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "metrics_token")

    def exists_by_token_prefix(self, token_prefix: str) -> bool:
        return self.exists_where("token_prefix = :token_prefix", {"token_prefix": token_prefix})

    def exists_active_by_project(self, project: PersistedObject) -> bool:
        return self.exists_where(
            "project_id = :project_id AND is_active = true",
            {"project_id": project.id},
        )


class EventTypeProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "event_type")

    def exists_by_project_and_code(self, project: PersistedObject, code: str) -> bool:
        return self.exists_where(
            "project_id = :project_id AND code = :code",
            {"project_id": project.id, "code": code},
        )

    def exists_active_by_project_and_code(self, project: PersistedObject, code: str) -> bool:
        return self.exists_where(
            "project_id = :project_id AND code = :code AND is_active = true",
            {"project_id": project.id, "code": code},
        )


class SchemaDefinitionProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "schema_definition")

    def exists_by_event_type_and_version(
        self,
        event_type: PersistedObject,
        json_version_internal: str,
    ) -> bool:
        return self.exists_where(
            "event_type_id = :event_type_id AND json_version_internal = :version",
            {"event_type_id": event_type.id, "version": json_version_internal},
        )

    def exists_active_by_event_type(self, event_type: PersistedObject) -> bool:
        return self.exists_where(
            "event_type_id = :event_type_id AND is_active = true",
            {"event_type_id": event_type.id},
        )


class RouteDefinitionProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "route_definition")

    def exists_by_event_type_routing_key_and_destination(
        self,
        event_type: PersistedObject,
        routing_key: str,
        destination_url: str,
    ) -> bool:
        return self.exists_where(
            """
            event_type_id = :event_type_id
            AND routing_key = :routing_key
            AND destination_url = :destination_url
            """,
            {
                "event_type_id": event_type.id,
                "routing_key": routing_key,
                "destination_url": destination_url,
            },
        )

    def exists_active_by_event_type(self, event_type: PersistedObject) -> bool:
        return self.exists_where(
            "event_type_id = :event_type_id AND is_active = true",
            {"event_type_id": event_type.id},
        )


class EventProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "event")

    def exists_by_uuid(self, event_uuid: str) -> bool:
        return self.exists_where("event_uuid = :event_uuid", {"event_uuid": event_uuid})

    def exists_by_status(self, status: str) -> bool:
        return self.exists_where("status = :status", {"status": status})

    def exists_by_correlation_id(self, correlation_id: str) -> bool:
        return self.exists_where(
            "correlation_id = :correlation_id",
            {"correlation_id": correlation_id},
        )


class EventDeliveryProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "event_delivery")

    def exists_by_event_and_destination(self, event: PersistedObject, destination_name: str) -> bool:
        return self.exists_where(
            "event_id = :event_id AND destination_name = :destination_name",
            {"event_id": event.id, "destination_name": destination_name},
        )

    def exists_by_status(self, status: str) -> bool:
        return self.exists_where("status = :status", {"status": status})


class MetricDefinitionProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "metric_definition")

    def exists_by_event_type_and_code(self, event_type: PersistedObject, code: str) -> bool:
        return self.exists_where(
            "event_type_id = :event_type_id AND code = :code",
            {"event_type_id": event_type.id, "code": code},
        )

    def exists_active_by_event_type_and_code(self, event_type: PersistedObject, code: str) -> bool:
        return self.exists_where(
            "event_type_id = :event_type_id AND code = :code AND is_active = true",
            {"event_type_id": event_type.id, "code": code},
        )


class MetricDefinitionVersionProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "metric_definition_version")

    def exists_by_metric_definition_and_version(
        self,
        metric_definition: PersistedObject,
        yaml_version_number: int,
    ) -> bool:
        return self.exists_where(
            """
            metric_definition_id = :metric_definition_id
            AND yaml_version_number = :yaml_version_number
            """,
            {
                "metric_definition_id": metric_definition.id,
                "yaml_version_number": yaml_version_number,
            },
        )

    def exists_active_by_metric_definition(self, metric_definition: PersistedObject) -> bool:
        return self.exists_where(
            "metric_definition_id = :metric_definition_id AND is_active = true",
            {"metric_definition_id": metric_definition.id},
        )


class MetricDefinitionVersionSchemaProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "metric_definition_version_schema")

    def exists_by_version_and_schema(
        self,
        metric_definition_version: PersistedObject,
        schema_definition: PersistedObject,
    ) -> bool:
        return self.exists_where(
            """
            metric_definition_version_id = :metric_definition_version_id
            AND schema_definition_id = :schema_definition_id
            """,
            {
                "metric_definition_version_id": metric_definition_version.id,
                "schema_definition_id": schema_definition.id,
            },
        )


class ProcessingChainProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "processing_chain")

    def exists_by_scope_and_version(
        self,
        event_type: PersistedObject,
        schema_definition: PersistedObject,
        version_number: int,
    ) -> bool:
        return self.exists_where(
            """
            event_type_id = :event_type_id
            AND schema_definition_id = :schema_definition_id
            AND version_number = :version_number
            """,
            {
                "event_type_id": event_type.id,
                "schema_definition_id": schema_definition.id,
                "version_number": version_number,
            },
        )

    def exists_active_by_scope(
        self,
        event_type: PersistedObject,
        schema_definition: PersistedObject,
    ) -> bool:
        return self.exists_where(
            """
            event_type_id = :event_type_id
            AND schema_definition_id = :schema_definition_id
            AND is_active = true
            """,
            {
                "event_type_id": event_type.id,
                "schema_definition_id": schema_definition.id,
            },
        )


class ProcessingPlanProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "processing_plan")

    def exists_by_chain_and_metric_definition(
        self,
        processing_chain: PersistedObject,
        metric_definition: PersistedObject,
    ) -> bool:
        return self.exists_where(
            """
            processing_chain_id = :processing_chain_id
            AND metric_definition_id = :metric_definition_id
            """,
            {
                "processing_chain_id": processing_chain.id,
                "metric_definition_id": metric_definition.id,
            },
        )


class AnalyticalObservationProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "analytical_observation")

    def exists_by_event_and_metric_code(self, event: PersistedObject, metric_code: str) -> bool:
        return self.exists_where(
            "event_id = :event_id AND metric_code = :metric_code",
            {"event_id": event.id, "metric_code": metric_code},
        )


class MetricStateProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "metric_state")

    def exists_by_series(
        self,
        project: PersistedObject,
        event_type: PersistedObject,
        metric_code: str,
        labels_hash: str,
    ) -> bool:
        return self.exists_where(
            """
            project_id = :project_id
            AND event_type_id = :event_type_id
            AND metric_code = :metric_code
            AND labels_hash = :labels_hash
            """,
            {
                "project_id": project.id,
                "event_type_id": event_type.id,
                "metric_code": metric_code,
                "labels_hash": labels_hash,
            },
        )


class MetricCheckpointProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "metric_checkpoint")

    def exists_by_name(self, checkpoint_name: str) -> bool:
        return self.exists_where(
            "checkpoint_name = :checkpoint_name",
            {"checkpoint_name": checkpoint_name},
        )


class SystemMetricProbe(BaseProbe):
    def __init__(self, connection: Connection):
        super().__init__(connection, "system_metric")

    def exists_by_metric_code_and_period(
        self,
        metric_code: str,
        period_start: datetime,
        period_end: datetime,
    ) -> bool:
        return self.exists_where(
            """
            metric_code = :metric_code
            AND period_start = :period_start
            AND period_end = :period_end
            """,
            {
                "metric_code": metric_code,
                "period_start": period_start,
                "period_end": period_end,
            },
        )