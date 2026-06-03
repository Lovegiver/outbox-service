from __future__ import annotations

from app.models.metric_definition import MetricDefinition
from app.models.metric_definition_version import MetricDefinitionVersion
from sqlalchemy.orm import Session


class MetricDefinitionAdminService:
    """
    Service responsible for administrative creation of analytical metric
    definitions and YAML versions.
    """

    def __init__(self, db: Session) -> None:
        """
        Initialize the service.

        Args:
            db: SQLAlchemy session used to persist metric configuration objects.
        """
        self.db = db

    def create_metric_definition(
        self,
        event_type_id: int,
        code: str,
        name: str,
        description: str | None,
    ) -> MetricDefinition:
        """
        Create a metric definition for an EventType.

        Args:
            event_type_id: EventType that owns the metric definition.
            code: Stable technical code of the metric definition.
            name: Human-readable name.
            description: Optional human-readable description.

        Returns:
            The persisted MetricDefinition.
        """
        metric_definition = MetricDefinition(
            event_type_id=event_type_id,
            code=code,
            name=name,
            description=description,
            is_active=True,
        )

        self.db.add(metric_definition)
        self.db.commit()
        self.db.refresh(metric_definition)

        return metric_definition

    def create_metric_definition_version(
        self,
        metric_definition_id: int,
        yaml_version_number: int,
        yaml_version_label: str | None,
        yaml_content: str,
    ) -> MetricDefinitionVersion:
        """
        Create a YAML version for an existing metric definition.

        Args:
            metric_definition_id: MetricDefinition owning the YAML version.
            yaml_version_number: Internal monotonically increasing version number.
            yaml_version_label: Optional display label.
            yaml_content: Raw YAML projection content.

        Returns:
            The persisted MetricDefinitionVersion.
        """
        metric_definition_version = MetricDefinitionVersion(
            metric_definition_id=metric_definition_id,
            yaml_version_number=yaml_version_number,
            yaml_version_label=yaml_version_label,
            yaml_content=yaml_content,
            is_active=True,
        )

        self.db.add(metric_definition_version)
        self.db.commit()
        self.db.refresh(metric_definition_version)

        return metric_definition_version