from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal, engine
from app.models.metric_definition_version import MetricDefinitionVersion
from app.models.processing_chain import ProcessingChain
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.metric_definition_version_schema_repository import (
    MetricDefinitionVersionSchemaRepository,
)
from app.repositories.processing_chain_repository import ProcessingChainRepository
from app.repositories.processing_plan_repository import ProcessingPlanRepository
from app.repositories.schema_repository import SchemaRepository
from app.services.metric_yaml_service import MetricYamlService
from app.services.processing_chain_activation_service import (
    ProcessingChainActivationService,
)
from app.services.processing_chain_builder_service import (
    ProcessingChainBuilderService,
)
from app.services.processing_chain_errors import ProcessingChainIncompleteError
from app.services.schema_metric_propagation_service import (
    SchemaMetricPropagationService,
)
from tests.domain.record import (
    EventTypeRecord,
    MetricDefinitionRecord,
    MetricDefinitionVersionRecord,
    MetricDefinitionVersionSchemaRecord,
    ProcessingChainRecord,
    ProcessingPlanRecord,
    ProjectRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.object_factory import ObjectFactory


YAML_V1 = """version: "1.0"
observations:
  - code: sales_total
    transform: identity
    value_path: $.amount
"""
YAML_V2 = """version: "1.0"
observations:
  - code: sales_total
    transform: identity
    value_path: $.amount
    labels:
      country: $.country
"""
JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number"},
        "country": {"type": "string"},
    },
    "required": ["amount", "country"],
}


class ExplicitVersionRepository(MetricDefinitionVersionRepository):
    """Select one fixed version so two concurrent rebuilds differ."""

    def __init__(self, db, version_id: int) -> None:
        super().__init__(db)
        self.version_id = version_id

    def find_latest_compatible_versions(self, **_kwargs):
        version = self.find_by_id(self.version_id)
        assert version is not None
        return [version]


class PostLockFailingBuilder(ProcessingChainBuilderService):
    """Fail only after the activation service has locked the schema scope."""

    def persist_chain(self, *args, **kwargs):
        raise RuntimeError("snapshot persistence failed after schema lock")


class FailSecondCompatibilityRepository(
    MetricDefinitionVersionSchemaRepository
):
    """Fail after one compatibility row has been flushed."""

    def __init__(self, db) -> None:
        super().__init__(db)
        self.add_count = 0

    def add(self, compatibility):
        self.add_count += 1
        if self.add_count == 2:
            raise RuntimeError("compatibility persistence interrupted")
        return super().add(compatibility)


def _service(session, version_id: int, *, fail_after_lock: bool = False):
    chain_repository = ProcessingChainRepository(session)
    plan_repository = ProcessingPlanRepository(session)
    builder_type = PostLockFailingBuilder if fail_after_lock else ProcessingChainBuilderService
    builder = builder_type(
        processing_chain_repository=chain_repository,
        processing_plan_repository=plan_repository,
        compatibility_repository=MetricDefinitionVersionSchemaRepository(session),
        metric_yaml_service=MetricYamlService(),
    )
    return ProcessingChainActivationService(
        db=session,
        processing_chain_repository=chain_repository,
        processing_plan_repository=plan_repository,
        metric_definition_version_repository=ExplicitVersionRepository(
            session, version_id
        ),
        schema_repository=SchemaRepository(session),
        processing_chain_builder_service=builder,
    )


def _fixture_graph(prefix: str):
    suffix = uuid4().hex
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"{prefix}-{suffix}"))
        event_type = factory.event_type(
            EventTypeRecord(
                project=project,
                code=f"{prefix}.{suffix}",
                name="Processing chain concurrency",
            )
        )
        schema = factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema=JSON_SCHEMA,
                json_version_internal="1",
            )
        )
        definition = factory.metric_definition(
            MetricDefinitionRecord(
                event_type=event_type,
                code="sales",
                name="Sales",
            )
        )
        version_one = factory.metric_definition_version(
            MetricDefinitionVersionRecord(
                metric_definition=definition,
                yaml_version_number=1,
                yaml_content=YAML_V1,
            )
        )
        version_two = factory.metric_definition_version(
            MetricDefinitionVersionRecord(
                metric_definition=definition,
                yaml_version_number=2,
                yaml_content=YAML_V2,
            )
        )
        factory.metric_definition_version_schema(
            MetricDefinitionVersionSchemaRecord(version_one, schema)
        )
        factory.metric_definition_version_schema(
            MetricDefinitionVersionSchemaRecord(version_two, schema)
        )
    return project, event_type, schema, definition, version_one, version_two


def _cleanup(project, event_type, schema, definition) -> None:
    with engine.begin() as connection:
        params = {
            "project_id": project.id,
            "event_type_id": event_type.id,
            "schema_id": schema.id,
            "definition_id": definition.id,
        }
        connection.execute(
            text(
                "DELETE FROM outbox.processing_plan WHERE processing_chain_id IN "
                "(SELECT id FROM outbox.processing_chain WHERE schema_definition_id = :schema_id)"
            ),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.processing_chain WHERE schema_definition_id = :schema_id"),
            params,
        )
        connection.execute(
            text(
                "DELETE FROM outbox.metric_definition_version_schema "
                "WHERE schema_definition_id = :schema_id"
            ),
            params,
        )
        connection.execute(
            text(
                "DELETE FROM outbox.metric_definition_version "
                "WHERE metric_definition_id = :definition_id"
            ),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.metric_definition WHERE id = :definition_id"),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.schema_definition WHERE id = :schema_id"),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.event_type WHERE id = :event_type_id"),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.project WHERE id = :project_id"),
            params,
        )


def _cleanup_event_type(project_id: int, event_type_id: int) -> None:
    """Remove a complete isolated metric configuration graph."""
    with engine.begin() as connection:
        params = {"event_type_id": event_type_id, "project_id": project_id}
        connection.execute(
            text(
                "DELETE FROM outbox.processing_plan WHERE processing_chain_id IN "
                "(SELECT id FROM outbox.processing_chain WHERE event_type_id = :event_type_id)"
            ),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.processing_chain WHERE event_type_id = :event_type_id"),
            params,
        )
        connection.execute(
            text(
                "DELETE FROM outbox.metric_definition_version_schema WHERE "
                "metric_definition_version_id IN (SELECT v.id FROM "
                "outbox.metric_definition_version v JOIN outbox.metric_definition d "
                "ON d.id = v.metric_definition_id WHERE d.event_type_id = :event_type_id)"
            ),
            params,
        )
        connection.execute(
            text(
                "DELETE FROM outbox.metric_definition_version WHERE "
                "metric_definition_id IN (SELECT id FROM outbox.metric_definition "
                "WHERE event_type_id = :event_type_id)"
            ),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.metric_definition WHERE event_type_id = :event_type_id"),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.schema_definition WHERE event_type_id = :event_type_id"),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.event_type WHERE id = :event_type_id"),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.project WHERE id = :project_id"),
            params,
        )


def test_concurrent_changed_rebuilds_get_unique_consecutive_versions() -> None:
    graph = _fixture_graph("chain-build")
    project, event_type, schema, definition, version_one, version_two = graph
    barrier = Barrier(2)

    def rebuild(version_id: int) -> int:
        with SessionLocal() as session:
            service = _service(session, version_id)
            barrier.wait(timeout=10)
            return service.rebuild_chain(
                event_type.id, schema.id
            ).version_number

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(rebuild, version_one.id),
                executor.submit(rebuild, version_two.id),
            ]
            created_versions = [future.result(timeout=20) for future in futures]

        with SessionLocal() as session:
            persisted_versions = list(
                session.scalars(
                    select(ProcessingChain.version_number)
                    .where(ProcessingChain.schema_definition_id == schema.id)
                    .order_by(ProcessingChain.version_number)
                )
            )
            active_count = session.scalar(
                select(func.count(ProcessingChain.id)).where(
                    ProcessingChain.schema_definition_id == schema.id,
                    ProcessingChain.is_active.is_(True),
                )
            )

        assert sorted(created_versions) == [1, 2]
        assert persisted_versions == [1, 2]
        assert active_count == 0
    finally:
        _cleanup(project, event_type, schema, definition)


def test_post_lock_failure_rolls_back_and_releases_schema_lock() -> None:
    graph = _fixture_graph("chain-recovery")
    project, event_type, schema, definition, version_one, _ = graph

    try:
        with SessionLocal() as failing_session:
            with pytest.raises(RuntimeError, match="after schema lock"):
                _service(
                    failing_session,
                    version_one.id,
                    fail_after_lock=True,
                ).rebuild_chain(event_type.id, schema.id)
            assert failing_session.in_transaction() is False

        with SessionLocal() as recovery_session:
            recovery_session.execute(text("SET LOCAL lock_timeout = '1s'"))
            chain = _service(
                recovery_session, version_one.id
            ).rebuild_chain(event_type.id, schema.id)
            assert chain.version_number == 1
            assert chain.status == "DRAFT"
            assert chain.is_active is False

        with SessionLocal() as verification_session:
            assert verification_session.scalar(
                select(func.count(ProcessingChain.id)).where(
                    ProcessingChain.schema_definition_id == schema.id
                )
            ) == 1
    finally:
        _cleanup(project, event_type, schema, definition)


def test_concurrent_activations_leave_exactly_one_active_chain() -> None:
    graph = _fixture_graph("chain-activate")
    project, event_type, schema, definition, version_one, _ = graph
    compiled = MetricYamlService().compile(YAML_V1, JSON_SCHEMA).compiled_plan_json
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        candidates = []
        for version_number in (1, 2):
            candidate = factory.processing_chain(
                ProcessingChainRecord(
                    event_type=event_type,
                    schema_definition=schema,
                    version_number=version_number,
                )
            )
            factory.processing_plan(
                ProcessingPlanRecord(
                    processing_chain=candidate,
                    metric_definition=definition,
                    metric_definition_version=version_one,
                    compiled_plan_json=compiled,
                )
            )
            candidates.append(candidate)
    barrier = Barrier(2)

    def activate(chain_id: int) -> int:
        with SessionLocal() as session:
            barrier.wait(timeout=10)
            return _service(session, version_one.id).activate_chain(
                event_type.id,
                schema.id,
                chain_id,
            ).id

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(activate, candidate.id)
                for candidate in candidates
            ]
            activated_ids = [future.result(timeout=20) for future in futures]

        with SessionLocal() as session:
            rows = list(
                session.execute(
                    select(
                        ProcessingChain.id,
                        ProcessingChain.status,
                        ProcessingChain.is_active,
                    )
                    .where(ProcessingChain.schema_definition_id == schema.id)
                    .order_by(ProcessingChain.version_number)
                )
            )

        assert set(activated_ids) == {candidate.id for candidate in candidates}
        assert sum(row.is_active for row in rows) == 1
        assert sorted(row.status for row in rows) == ["ACTIVE", "RETIRED"]
    finally:
        _cleanup(project, event_type, schema, definition)


def test_failed_activation_rolls_back_and_releases_scope_lock() -> None:
    graph = _fixture_graph("activation-recovery")
    project, event_type, schema, definition, version_one, _ = graph
    compiled = MetricYamlService().compile(YAML_V1, JSON_SCHEMA).compiled_plan_json
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        active = factory.processing_chain(
            ProcessingChainRecord(
                event_type=event_type,
                schema_definition=schema,
                version_number=1,
                status="ACTIVE",
                is_active=True,
            )
        )
        factory.processing_plan(
            ProcessingPlanRecord(
                processing_chain=active,
                metric_definition=definition,
                metric_definition_version=version_one,
                compiled_plan_json=compiled,
            )
        )
        candidate = factory.processing_chain(
            ProcessingChainRecord(
                event_type=event_type,
                schema_definition=schema,
                version_number=2,
            )
        )
        broken_plan = factory.processing_plan(
            ProcessingPlanRecord(
                processing_chain=candidate,
                metric_definition=definition,
                metric_definition_version=version_one,
                compiled_plan_json=None,
            )
        )

    try:
        with SessionLocal() as failing_session:
            with pytest.raises(
                ProcessingChainIncompleteError,
                match="incomplete ProcessingPlans",
            ):
                _service(failing_session, version_one.id).activate_chain(
                    event_type.id,
                    schema.id,
                    candidate.id,
                )
            assert failing_session.in_transaction() is False

        with SessionLocal() as verification:
            current = ProcessingChainRepository(verification).find_active(
                event_type.id,
                schema.id,
            )
            assert current is not None
            assert current.id == active.id

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE outbox.processing_plan "
                    "SET compiled_plan_json = CAST(:compiled AS jsonb) "
                    "WHERE id = :plan_id"
                ),
                {
                    "compiled": json.dumps(compiled),
                    "plan_id": broken_plan.id,
                },
            )

        with SessionLocal() as recovery_session:
            recovery_session.execute(text("SET LOCAL lock_timeout = '1s'"))
            activated = _service(
                recovery_session,
                version_one.id,
            ).activate_chain(event_type.id, schema.id, candidate.id)
            assert activated.id == candidate.id

        with SessionLocal() as final_session:
            rows = list(
                final_session.execute(
                    select(
                        ProcessingChain.id,
                        ProcessingChain.status,
                        ProcessingChain.is_active,
                    )
                    .where(ProcessingChain.schema_definition_id == schema.id)
                    .order_by(ProcessingChain.version_number)
                )
            )
            assert [(row.status, row.is_active) for row in rows] == [
                ("RETIRED", False),
                ("ACTIVE", True),
            ]
    finally:
        _cleanup(project, event_type, schema, definition)


def test_database_partial_index_rejects_two_active_chains_in_one_scope() -> None:
    graph = _fixture_graph("chain-index")
    project, event_type, schema, definition, version_one, _ = graph
    compiled = MetricYamlService().compile(YAML_V1, JSON_SCHEMA).compiled_plan_json

    try:
        with engine.begin() as connection:
            factory = ObjectFactory(connection)
            first = factory.processing_chain(
                ProcessingChainRecord(
                    event_type=event_type,
                    schema_definition=schema,
                    version_number=1,
                    status="ACTIVE",
                    is_active=True,
                )
            )
            factory.processing_plan(
                ProcessingPlanRecord(
                    processing_chain=first,
                    metric_definition=definition,
                    metric_definition_version=version_one,
                    compiled_plan_json=compiled,
                )
            )

        with pytest.raises(
            IntegrityError,
            match="uq_processing_chain_active_scope",
        ):
            with engine.begin() as connection:
                ObjectFactory(connection).processing_chain(
                    ProcessingChainRecord(
                        event_type=event_type,
                        schema_definition=schema,
                        version_number=2,
                        status="ACTIVE",
                        is_active=True,
                    )
                )
    finally:
        _cleanup(project, event_type, schema, definition)


def test_propagation_persistence_failure_rolls_back_every_new_compatibility() -> None:
    graph = _fixture_graph("propagation-rollback")
    project, event_type, source_schema, first_definition, first_version, _ = graph
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        target_schema = factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema=JSON_SCHEMA,
                json_version_internal="2",
            )
        )
        second_definition = factory.metric_definition(
            MetricDefinitionRecord(
                event_type=event_type,
                code="orders",
                name="Orders",
            )
        )
        second_version = factory.metric_definition_version(
            MetricDefinitionVersionRecord(
                metric_definition=second_definition,
                yaml_version_number=1,
                yaml_content=YAML_V1.replace("sales_total", "orders_total"),
            )
        )
        factory.metric_definition_version_schema(
            MetricDefinitionVersionSchemaRecord(second_version, source_schema)
        )
        source_chain = factory.processing_chain(
            ProcessingChainRecord(
                event_type=event_type,
                schema_definition=source_schema,
                version_number=1,
                status="ACTIVE",
                is_active=True,
            )
        )
        for position, (definition, version, yaml_content) in enumerate(
            [
                (first_definition, first_version, YAML_V1),
                (
                    second_definition,
                    second_version,
                    YAML_V1.replace("sales_total", "orders_total"),
                ),
            ]
        ):
            factory.processing_plan(
                ProcessingPlanRecord(
                    processing_chain=source_chain,
                    metric_definition=definition,
                    metric_definition_version=version,
                    position=position,
                    compiled_plan_json=(
                        MetricYamlService()
                        .compile(yaml_content, JSON_SCHEMA)
                        .compiled_plan_json
                    ),
                )
            )

    try:
        with SessionLocal() as session:
            compatibility_repository = FailSecondCompatibilityRepository(session)
            builder = ProcessingChainBuilderService(
                processing_chain_repository=ProcessingChainRepository(session),
                processing_plan_repository=ProcessingPlanRepository(session),
                compatibility_repository=compatibility_repository,
                metric_yaml_service=MetricYamlService(),
            )
            service = SchemaMetricPropagationService(
                db=session,
                schema_repository=SchemaRepository(session),
                processing_chain_repository=ProcessingChainRepository(session),
                processing_plan_repository=ProcessingPlanRepository(session),
                metric_definition_version_repository=(
                    MetricDefinitionVersionRepository(session)
                ),
                compatibility_repository=compatibility_repository,
                metric_yaml_service=MetricYamlService(),
                processing_chain_builder_service=builder,
            )
            with pytest.raises(
                RuntimeError,
                match="compatibility persistence interrupted",
            ):
                service.propagate(
                    event_type.id,
                    source_schema.id,
                    target_schema.id,
                )
            assert session.in_transaction() is False

        with SessionLocal() as verification:
            compatibility_count = verification.scalar(
                text(
                    "SELECT COUNT(*) FROM outbox.metric_definition_version_schema "
                    "WHERE schema_definition_id = :schema_id"
                ),
                {"schema_id": target_schema.id},
            )
            candidate_count = verification.scalar(
                select(func.count(ProcessingChain.id)).where(
                    ProcessingChain.schema_definition_id == target_schema.id
                )
            )
        assert compatibility_count == 0
        assert candidate_count == 0
    finally:
        _cleanup_event_type(project.id, event_type.id)
