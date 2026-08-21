"""Canonical validation and persistence of YAML/schema compatibilities."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.metric_definition_version_schema import (
    MetricDefinitionVersionSchema,
)
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.metric_definition_version_schema_repository import (
    MetricDefinitionVersionSchemaRepository,
)
from app.repositories.schema_repository import SchemaRepository
from app.services.metric_definition_admin_service import (
    MetricConfigurationNotFoundError,
    MetricConfigurationScopeError,
)
from app.services.metric_yaml_service import MetricYamlService


class MetricDefinitionVersionSchemaService:
    """Register proven compatibilities without rebuilding runtime snapshots."""

    def __init__(
        self,
        db: Session,
        compatibility_repository: MetricDefinitionVersionSchemaRepository,
        metric_definition_version_repository: MetricDefinitionVersionRepository,
        schema_repository: SchemaRepository,
        metric_yaml_service: MetricYamlService,
    ) -> None:
        self.db = db
        self.compatibility_repository = compatibility_repository
        self.metric_definition_version_repository = (
            metric_definition_version_repository
        )
        self.schema_repository = schema_repository
        self.metric_yaml_service = metric_yaml_service

    def create_compatibility(
        self,
        event_type_id: int,
        metric_definition_version_id: int,
        schema_definition_id: int,
    ) -> MetricDefinitionVersionSchema:
        """Revalidate persisted YAML and idempotently materialize compatibility."""
        try:
            metric_version = self.metric_definition_version_repository.find_by_id(
                metric_definition_version_id
            )
            if metric_version is None:
                raise MetricConfigurationNotFoundError(
                    "MetricDefinitionVersion "
                    f"{metric_definition_version_id} not found"
                )
            schema_definition = self.schema_repository.find_by_id(
                schema_definition_id
            )
            if schema_definition is None:
                raise MetricConfigurationNotFoundError(
                    f"SchemaDefinition {schema_definition_id} not found"
                )
            if metric_version.metric_definition.event_type_id != event_type_id:
                raise MetricConfigurationScopeError(
                    "MetricDefinitionVersion belongs to another EventType"
                )
            if schema_definition.event_type_id != event_type_id:
                raise MetricConfigurationScopeError(
                    "SchemaDefinition belongs to another EventType"
                )

            self.metric_yaml_service.compile(
                yaml_content=metric_version.yaml_content,
                json_schema=schema_definition.json_schema,
            )

            self.schema_repository.find_by_id(
                schema_definition_id,
                for_update=True,
            )
            existing = self.compatibility_repository.find_by_version_and_schema(
                metric_definition_version_id=metric_definition_version_id,
                schema_definition_id=schema_definition_id,
            )
            if existing is not None:
                self.db.commit()
                return existing

            compatibility = self.compatibility_repository.add(
                MetricDefinitionVersionSchema(
                    metric_definition_version_id=metric_definition_version_id,
                    schema_definition_id=schema_definition_id,
                )
            )
            self.db.commit()
            self.db.refresh(compatibility)
            return compatibility
        except IntegrityError:
            self.db.rollback()
            existing = self.compatibility_repository.find_by_version_and_schema(
                metric_definition_version_id=metric_definition_version_id,
                schema_definition_id=schema_definition_id,
            )
            if existing is None:
                raise
            return existing
        except Exception:
            self.db.rollback()
            raise
