from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.metric_definition_version_schema import (
    MetricDefinitionVersionSchema,
)


class MetricDefinitionVersionSchemaRepository:
    """
    Repository dedicated to YAML/schema compatibility records.

    A MetricDefinitionVersionSchema row means that a given YAML metric
    definition version has been validated as compatible with a specific
    JSON SchemaDefinition.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the repository.

        Args:
            db: SQLAlchemy session used to access the database.
        """
        self.db = db

    def add(
        self,
        compatibility: MetricDefinitionVersionSchema,
    ) -> MetricDefinitionVersionSchema:
        """
        Persist a YAML/schema compatibility record.

        Args:
            compatibility: Compatibility entity to persist.

        Returns:
            The persisted compatibility entity.
        """
        self.db.add(compatibility)
        self.db.flush()
        return compatibility

    def find_by_version_and_schema(
        self,
        metric_definition_version_id: int,
        schema_definition_id: int,
    ) -> MetricDefinitionVersionSchema | None:
        """
        Find an existing compatibility for a YAML version and schema.

        Args:
            metric_definition_version_id: MetricDefinitionVersion identifier.
            schema_definition_id: SchemaDefinition identifier.

        Returns:
            The compatibility entity when it exists, otherwise None.
        """
        statement = select(MetricDefinitionVersionSchema).where(
            MetricDefinitionVersionSchema.metric_definition_version_id
            == metric_definition_version_id,
            MetricDefinitionVersionSchema.schema_definition_id
            == schema_definition_id,
        )

        return self.db.execute(statement).scalar_one_or_none()

    def list_by_schema(
        self,
        schema_definition_id: int,
    ) -> list[MetricDefinitionVersionSchema]:
        """Return compatibility rows in deterministic version order."""
        statement = (
            select(MetricDefinitionVersionSchema)
            .where(
                MetricDefinitionVersionSchema.schema_definition_id
                == schema_definition_id
            )
            .order_by(
                MetricDefinitionVersionSchema.metric_definition_version_id.asc()
            )
        )
        return list(self.db.execute(statement).scalars().all())
