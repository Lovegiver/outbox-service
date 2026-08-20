from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.container.service_factory import ServiceFactory
from app.database import SessionLocal, engine
from app.models.metric_definition_version import MetricDefinitionVersion
from app.repositories.metric_definition_repository import (
    MetricDefinitionRepository,
)
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.schema_repository import SchemaRepository
from app.services.metric_definition_admin_service import (
    MetricDefinitionAdminService,
)
from app.services.metric_yaml_service import MetricYamlService
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


class FailingNextVersionRepository(MetricDefinitionVersionRepository):
    """Fail after the owning service has acquired the definition lock."""

    def find_next_version_number(self, _metric_definition_id: int) -> int:
        """Simulate a post-lock failure before any version can be inserted."""
        raise RuntimeError("version lookup failed after lock")


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


def test_post_lock_failure_rolls_back_and_does_not_block_recovery() -> None:
    suffix = uuid4().hex

    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"yaml-recovery-{suffix}"))
        event_type = factory.event_type(
            EventTypeRecord(
                project=project,
                code=f"yaml.recovery.{suffix}",
                name="YAML version recovery",
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
                code="recovery_metrics",
                name="Recovery metrics",
            )
        )

    try:
        with SessionLocal() as failing_session:
            failing_service = MetricDefinitionAdminService(
                db=failing_session,
                metric_definition_repository=MetricDefinitionRepository(
                    failing_session
                ),
                metric_definition_version_repository=(
                    FailingNextVersionRepository(failing_session)
                ),
                schema_repository=SchemaRepository(failing_session),
                metric_yaml_service=MetricYamlService(),
            )

            with pytest.raises(
                RuntimeError,
                match="version lookup failed after lock",
            ):
                failing_service.create_metric_definition_version(
                    event_type_id=event_type.id,
                    metric_definition_id=metric_definition.id,
                    schema_definition_id=schema.id,
                    yaml_version_label="failed",
                    yaml_content=VALID_YAML,
                )

            assert failing_session.in_transaction() is False

            with SessionLocal() as verification_session:
                persisted_count = verification_session.scalar(
                    select(func.count(MetricDefinitionVersion.id)).where(
                        MetricDefinitionVersion.metric_definition_id
                        == metric_definition.id
                    )
                )
                assert persisted_count == 0

            with SessionLocal() as recovery_session:
                recovery_session.execute(text("SET LOCAL lock_timeout = '1s'"))
                recovery_service = (
                    ServiceFactory.create_metric_definition_admin_service(
                        recovery_session
                    )
                )
                recovered = recovery_service.create_metric_definition_version(
                    event_type_id=event_type.id,
                    metric_definition_id=metric_definition.id,
                    schema_definition_id=schema.id,
                    yaml_version_label="recovered",
                    yaml_content=VALID_YAML,
                )
                assert recovered.yaml_version_number == 1

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
