from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import func, select, text

from app.container.service_factory import ServiceFactory
from app.database import SessionLocal, engine
from app.models.metric_definition_version import MetricDefinitionVersion
from tests.domain.record import (
    EventTypeRecord,
    MetricDefinitionRecord,
    ProjectRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.object_factory import ObjectFactory


VALID_YAML = """version: "1.0"
observations:
  - code: concurrent_total
    transform: constant
"""


def test_concurrent_yaml_version_creation_assigns_unique_monotonic_numbers() -> None:
    suffix = uuid4().hex

    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"yaml-version-{suffix}"))
        event_type = factory.event_type(
            EventTypeRecord(
                project=project,
                code=f"yaml.version.{suffix}",
                name="Concurrent YAML version",
            )
        )
        schema = factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema={"type": "object", "properties": {}},
            )
        )
        metric_definition = factory.metric_definition(
            MetricDefinitionRecord(
                event_type=event_type,
                code="concurrent_metrics",
                name="Concurrent metrics",
            )
        )

    barrier = Barrier(2)

    def create_version(label: str) -> int:
        with SessionLocal() as session:
            service = ServiceFactory.create_metric_definition_admin_service(
                session
            )
            barrier.wait(timeout=10)
            version = service.create_metric_definition_version(
                event_type_id=event_type.id,
                metric_definition_id=metric_definition.id,
                schema_definition_id=schema.id,
                yaml_version_label=label,
                yaml_content=VALID_YAML,
            )
            return version.yaml_version_number

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(create_version, "first"),
                executor.submit(create_version, "second"),
            ]
            version_numbers = [future.result(timeout=20) for future in futures]

        with SessionLocal() as session:
            count = session.scalar(
                select(func.count(MetricDefinitionVersion.id)).where(
                    MetricDefinitionVersion.metric_definition_id
                    == metric_definition.id
                )
            )
            persisted_numbers = list(
                session.scalars(
                    select(MetricDefinitionVersion.yaml_version_number)
                    .where(
                        MetricDefinitionVersion.metric_definition_id
                        == metric_definition.id
                    )
                    .order_by(MetricDefinitionVersion.yaml_version_number)
                )
            )

        assert sorted(version_numbers) == [1, 2]
        assert count == 2
        assert persisted_numbers == [1, 2]

    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM outbox.metric_definition_version "
                    "WHERE metric_definition_id = :metric_definition_id"
                ),
                {"metric_definition_id": metric_definition.id},
            )
            connection.execute(
                text(
                    "DELETE FROM outbox.metric_definition "
                    "WHERE id = :metric_definition_id"
                ),
                {"metric_definition_id": metric_definition.id},
            )
            connection.execute(
                text(
                    "DELETE FROM outbox.schema_definition "
                    "WHERE id = :schema_definition_id"
                ),
                {"schema_definition_id": schema.id},
            )
            connection.execute(
                text("DELETE FROM outbox.event_type WHERE id = :event_type_id"),
                {"event_type_id": event_type.id},
            )
            connection.execute(
                text("DELETE FROM outbox.project WHERE id = :project_id"),
                {"project_id": project.id},
            )
