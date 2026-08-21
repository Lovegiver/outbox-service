from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.metric_definition_version_schema import MetricDefinitionVersionSchema


class MetricDefinitionVersionRepository:
    """Persist and load immutable YAML versions without owning transactions."""

    def __init__(self, db: Session) -> None:
        """Initialize the repository with its caller-owned session."""
        self.db = db

    def add(
        self,
        metric_definition_version: MetricDefinitionVersion,
    ) -> MetricDefinitionVersion:
        """Add a YAML version to the current transaction."""
        self.db.add(metric_definition_version)
        self.db.flush()
        return metric_definition_version

    def list_by_metric_definition(
        self,
        metric_definition_id: int,
    ) -> list[MetricDefinitionVersion]:
        """Return the complete YAML version history in ascending order."""
        statement = (
            select(MetricDefinitionVersion)
            .where(
                MetricDefinitionVersion.metric_definition_id
                == metric_definition_id
            )
            .order_by(
                MetricDefinitionVersion.yaml_version_number.asc(),
                MetricDefinitionVersion.id.asc(),
            )
        )

        return list(self.db.execute(statement).scalars().all())

    def find_next_version_number(self, metric_definition_id: int) -> int:
        """Return the next internal version number for a locked definition."""
        statement = select(
            func.max(MetricDefinitionVersion.yaml_version_number)
        ).where(
            MetricDefinitionVersion.metric_definition_id
            == metric_definition_id
        )
        current_max = self.db.execute(statement).scalar_one()
        return 1 if current_max is None else int(current_max) + 1

    def find_latest_compatible_versions(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> list[MetricDefinitionVersion]:
        latest_versions_subquery = (
            select(
                MetricDefinitionVersion.metric_definition_id.label(
                    "metric_definition_id"
                ),
                func.max(MetricDefinitionVersion.yaml_version_number).label(
                    "max_yaml_version_number"
                ),
            )
            .join(
                MetricDefinition,
                MetricDefinition.id == MetricDefinitionVersion.metric_definition_id,
            )
            .join(
                MetricDefinitionVersionSchema,
                MetricDefinitionVersionSchema.metric_definition_version_id
                == MetricDefinitionVersion.id,
            )
            .where(
                MetricDefinition.event_type_id == event_type_id,
                MetricDefinition.is_active.is_(True),
                MetricDefinitionVersion.is_active.is_(True),
                MetricDefinitionVersionSchema.schema_definition_id
                == schema_definition_id,
            )
            .group_by(MetricDefinitionVersion.metric_definition_id)
            .subquery()
        )

        statement = (
            select(MetricDefinitionVersion)
            .join(
                latest_versions_subquery,
                (
                    MetricDefinitionVersion.metric_definition_id
                    == latest_versions_subquery.c.metric_definition_id
                )
                & (
                    MetricDefinitionVersion.yaml_version_number
                    == latest_versions_subquery.c.max_yaml_version_number
                ),
            )
            .order_by(MetricDefinitionVersion.metric_definition_id)
        )

        return list(self.db.execute(statement).scalars().all())

    def find_by_id(
        self,
        metric_definition_version_id: int,
    ) -> MetricDefinitionVersion | None:
        """
        Find a metric definition version by its identifier.

        Args:
            metric_definition_version_id: Identifier of the YAML metric definition
                version to retrieve.

        Returns:
            The MetricDefinitionVersion when found, otherwise None.
        """
        statement = select(MetricDefinitionVersion).where(
            MetricDefinitionVersion.id == metric_definition_version_id
        )

        return self.db.execute(statement).scalar_one_or_none()

    def find_by_ids(
        self,
        metric_definition_version_ids: list[int],
    ) -> list[MetricDefinitionVersion]:
        """Return requested versions in deterministic definition/version order."""
        statement = (
            select(MetricDefinitionVersion)
            .where(MetricDefinitionVersion.id.in_(metric_definition_version_ids))
            .order_by(
                MetricDefinitionVersion.metric_definition_id.asc(),
                MetricDefinitionVersion.yaml_version_number.asc(),
                MetricDefinitionVersion.id.asc(),
            )
        )
        return list(self.db.execute(statement).scalars().all())
