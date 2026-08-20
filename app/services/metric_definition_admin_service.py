from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.schema_definition import SchemaDefinition
from app.repositories.metric_definition_repository import (
    MetricDefinitionRepository,
)
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.schema_repository import SchemaRepository
from app.services.metric_yaml_service import (
    MetricYamlCompilation,
    MetricYamlService,
)


class MetricConfigurationNotFoundError(ValueError):
    """Raised when a requested metric configuration resource is unknown."""


class MetricConfigurationScopeError(ValueError):
    """Raised when a resource belongs to another EventType scope."""


class MetricDefinitionAdminService:
    """Orchestrate metric definitions and immutable validated YAML versions."""

    def __init__(
        self,
        db: Session,
        metric_definition_repository: MetricDefinitionRepository,
        metric_definition_version_repository: MetricDefinitionVersionRepository,
        schema_repository: SchemaRepository,
        metric_yaml_service: MetricYamlService,
    ) -> None:
        """Initialize the service with caller-scoped persistence dependencies."""
        self.db = db
        self.metric_definition_repository = metric_definition_repository
        self.metric_definition_version_repository = (
            metric_definition_version_repository
        )
        self.schema_repository = schema_repository
        self.metric_yaml_service = metric_yaml_service

    def create_metric_definition(
        self,
        event_type_id: int,
        code: str,
        name: str,
        description: str | None,
    ) -> MetricDefinition:
        """Create an active metric definition for an EventType."""
        metric_definition = MetricDefinition(
            event_type_id=event_type_id,
            code=code,
            name=name,
            description=description,
            is_active=True,
        )

        try:
            self.metric_definition_repository.add(metric_definition)
            self.db.commit()
            self.db.refresh(metric_definition)
            return metric_definition
        except Exception:
            self.db.rollback()
            raise

    def list_metric_definitions(
        self,
        event_type_id: int,
    ) -> list[MetricDefinition]:
        """List metric definitions attached to an EventType."""
        return self.metric_definition_repository.list_by_event_type(event_type_id)

    def preview_metric_yaml(
        self,
        event_type_id: int,
        schema_definition_id: int,
        yaml_content: str,
    ) -> MetricYamlCompilation:
        """Compile metric YAML against an in-scope schema without writing."""
        schema_definition = self._get_schema_definition(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        )
        return self.metric_yaml_service.compile(
            yaml_content=yaml_content,
            json_schema=schema_definition.json_schema,
        )

    def create_metric_definition_version(
        self,
        event_type_id: int,
        metric_definition_id: int,
        schema_definition_id: int,
        yaml_version_label: str | None,
        yaml_content: str,
    ) -> MetricDefinitionVersion:
        """Validate and persist the next immutable YAML version atomically."""
        self._get_metric_definition(
            event_type_id=event_type_id,
            metric_definition_id=metric_definition_id,
        )
        schema_definition = self._get_schema_definition(
            event_type_id=event_type_id,
            schema_definition_id=schema_definition_id,
        )
        self.metric_yaml_service.compile(
            yaml_content=yaml_content,
            json_schema=schema_definition.json_schema,
        )

        try:
            metric_definition = self._get_metric_definition(
                event_type_id=event_type_id,
                metric_definition_id=metric_definition_id,
                for_update=True,
            )
            yaml_version_number = (
                self.metric_definition_version_repository
                .find_next_version_number(metric_definition.id)
            )
            version = MetricDefinitionVersion(
                metric_definition_id=metric_definition.id,
                yaml_version_number=yaml_version_number,
                yaml_version_label=yaml_version_label,
                yaml_content=yaml_content,
                is_active=True,
            )
            self.metric_definition_version_repository.add(version)
            self.db.commit()
            self.db.refresh(version)
            return version
        except Exception:
            self.db.rollback()
            raise

    def list_metric_definition_versions(
        self,
        event_type_id: int,
        metric_definition_id: int,
    ) -> list[MetricDefinitionVersion]:
        """Return one in-scope metric definition's immutable history."""
        metric_definition = self._get_metric_definition(
            event_type_id=event_type_id,
            metric_definition_id=metric_definition_id,
        )
        return self.metric_definition_version_repository.list_by_metric_definition(
            metric_definition.id
        )

    def _get_metric_definition(
        self,
        event_type_id: int,
        metric_definition_id: int,
        *,
        for_update: bool = False,
    ) -> MetricDefinition:
        metric_definition = self.metric_definition_repository.find_by_id(
            metric_definition_id,
            for_update=for_update,
        )
        if metric_definition is None:
            raise MetricConfigurationNotFoundError(
                f"MetricDefinition id={metric_definition_id} not found"
            )
        if metric_definition.event_type_id != event_type_id:
            raise MetricConfigurationScopeError(
                f"MetricDefinition id={metric_definition_id} does not belong "
                f"to EventType id={event_type_id}"
            )
        return metric_definition

    def _get_schema_definition(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> SchemaDefinition:
        schema_definition = self.schema_repository.find_by_id(
            schema_definition_id
        )
        if schema_definition is None:
            raise MetricConfigurationNotFoundError(
                f"SchemaDefinition id={schema_definition_id} not found"
            )
        if schema_definition.event_type_id != event_type_id:
            raise MetricConfigurationScopeError(
                f"SchemaDefinition id={schema_definition_id} does not belong "
                f"to EventType id={event_type_id}"
            )
        return schema_definition
