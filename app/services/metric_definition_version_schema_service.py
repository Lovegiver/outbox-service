from __future__ import annotations
import yaml

from sqlalchemy.orm import Session

from app.metrics_engine.metric_yaml_validator import validate_metric_yaml
from app.models.metric_definition_version_schema import (
    MetricDefinitionVersionSchema,
)
from app.repositories.metric_definition_version_schema_repository import (
    MetricDefinitionVersionSchemaRepository,
)
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.schema_repository import SchemaRepository
from app.services.processing_chain_activation_service import (
    ProcessingChainActivationService,
)


class MetricDefinitionVersionSchemaService:
    """
    Service responsible for validating and registering YAML/schema compatibilities.

    This service is part of the configuration-time pipeline. It validates that a
    MetricDefinitionVersion YAML can safely be applied to a given SchemaDefinition,
    persists the compatibility, and rebuilds the runtime ProcessingChain for the
    corresponding EventType and SchemaDefinition.
    """

    def __init__(
        self,
        db: Session,
        compatibility_repository: MetricDefinitionVersionSchemaRepository,
        metric_definition_version_repository: MetricDefinitionVersionRepository,
        schema_repository: SchemaRepository,
        processing_chain_activation_service: ProcessingChainActivationService,
    ) -> None:
        """
        Initialize the service.

        Args:
            compatibility_repository: Repository used to persist compatibility rows.
            metric_definition_version_repository: Repository used to fetch YAML versions.
            schema_repository: Repository used to fetch JSON Schema definitions.
            processing_chain_activation_service: Service used to rebuild and activate
                the runtime processing chain after a successful compatibility creation.
        """
        self.db = db
        self.compatibility_repository = compatibility_repository
        self.metric_definition_version_repository = (
            metric_definition_version_repository
        )
        self.schema_repository = schema_repository
        self.processing_chain_activation_service = (
            processing_chain_activation_service
        )

    def create_compatibility(
        self,
        metric_definition_version_id: int,
        schema_definition_id: int,
    ) -> MetricDefinitionVersionSchema:
        """
        Validate and persist a compatibility between a YAML version and a JSON schema.

        Args:
            metric_definition_version_id: Identifier of the MetricDefinitionVersion
                containing the YAML projection.
            schema_definition_id: Identifier of the SchemaDefinition containing the
                JSON Schema contract.

        Returns:
            The persisted MetricDefinitionVersionSchema compatibility.

        Raises:
            ValueError: If the MetricDefinitionVersion or SchemaDefinition cannot be
                found, or if the compatibility already exists.
            MetricYamlValidationError: If the YAML is not compatible with the JSON
                schema.
        """
        existing_compatibility = (
            self.compatibility_repository.find_by_version_and_schema(
                metric_definition_version_id=metric_definition_version_id,
                schema_definition_id=schema_definition_id,
            )
        )

        if existing_compatibility is not None:
            raise ValueError(
                "Compatibility already exists for "
                f"metric_definition_version_id={metric_definition_version_id}, "
                f"schema_definition_id={schema_definition_id}"
            )

        metric_definition_version = (
            self.metric_definition_version_repository.find_by_id(
                metric_definition_version_id
            )
        )

        if metric_definition_version is None:
            raise ValueError(
                f"MetricDefinitionVersion {metric_definition_version_id} not found"
            )

        schema_definition = self.schema_repository.find_by_id(
            schema_definition_id
        )

        if schema_definition is None:
            raise ValueError(
                f"SchemaDefinition {schema_definition_id} not found"
            )

        metric_yaml = yaml.safe_load(
            metric_definition_version.yaml_content
        )

        validate_metric_yaml(
            metric_yaml=metric_yaml,
            json_schema=schema_definition.json_schema,
        )

        compatibility = MetricDefinitionVersionSchema(
            metric_definition_version_id=metric_definition_version_id,
            schema_definition_id=schema_definition_id,
        )

        saved_compatibility = self.compatibility_repository.add(
            compatibility
        )

        self.processing_chain_activation_service.rebuild_and_activate_chain(
            event_type_id=schema_definition.event_type_id,
            schema_definition_id=schema_definition.id,
        )

        self.db.commit()
        self.db.refresh(saved_compatibility)

        return saved_compatibility