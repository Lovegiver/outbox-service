"""PostgreSQL proofs for atomic and concurrent Metrics Builder creation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.container.service_factory import ServiceFactory
from app.database import SessionLocal, engine
from app.repositories.metric_definition_repository import (
    MetricDefinitionRepository,
)
from app.repositories.metric_definition_version_repository import (
    MetricDefinitionVersionRepository,
)
from app.repositories.metric_definition_version_schema_repository import (
    MetricDefinitionVersionSchemaRepository,
)
from app.services.metric_builder_errors import (
    MetricBuilderAlreadyExistsError,
    MetricBuilderNameCollisionError,
)
from tests.domain.record import (
    EventTypeRecord,
    ProjectRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.object_factory import ObjectFactory


BUILDER_SCHEMA = {
    "type": "object",
    "required": ["amount", "status"],
    "properties": {
        "amount": {"type": "number", "minimum": 0},
        "status": {"type": "string", "enum": ["new", "done"]},
    },
}


class _PostFlushDefinitionFailure(MetricDefinitionRepository):
    """Fail after the definition has been flushed in the current transaction."""

    def add(self, metric_definition):
        """Flush the row, then simulate a later orchestration failure."""
        super().add(metric_definition)
        raise RuntimeError("failure after definition flush")


class _PostFlushVersionFailure(MetricDefinitionVersionRepository):
    """Fail after the first immutable version has been flushed."""

    def add(self, metric_definition_version):
        """Flush the row, then simulate a later orchestration failure."""
        super().add(metric_definition_version)
        raise RuntimeError("failure after version flush")


class _PostFlushCompatibilityFailure(MetricDefinitionVersionSchemaRepository):
    """Fail after the exact compatibility has been flushed."""

    def add(self, compatibility):
        """Flush the row, then simulate a pre-commit failure."""
        super().add(compatibility)
        raise RuntimeError("failure after compatibility flush")


def _fixture_graph(prefix: str):
    suffix = uuid4().hex
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"{prefix}-{suffix}"))
        event_type = factory.event_type(
            EventTypeRecord(
                project=project,
                code=f"{prefix}.{suffix}",
                name="Atomic Builder event",
            )
        )
        schema = factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema=BUILDER_SCHEMA,
                json_version_internal="1",
            )
        )
    return project, event_type, schema


def _create(
    service,
    event_type_id: int,
    schema_id: int,
    *,
    code: str = "sales_total",
    name: str = "Sales total",
):
    return service.create_metric_from_builder(
        event_type_id=event_type_id,
        code=code,
        name=name,
        description="Atomic Counter",
        intent="sum_value",
        value_path="$.amount",
        labels={"status": "$.status"},
        schema_definition_id=schema_id,
        yaml_version_label="initial",
    )


def _service(session):
    return ServiceFactory.create_metric_builder_service(session)


def _counts(event_type_id: int) -> tuple[int, int, int, int, int]:
    with engine.connect() as connection:
        params = {"event_type_id": event_type_id}
        definition_count = connection.execute(
            text(
                "SELECT count(*) FROM outbox.metric_definition "
                "WHERE event_type_id=:event_type_id"
            ),
            params,
        ).scalar_one()
        version_count = connection.execute(
            text(
                "SELECT count(*) FROM outbox.metric_definition_version v "
                "JOIN outbox.metric_definition d ON d.id=v.metric_definition_id "
                "WHERE d.event_type_id=:event_type_id"
            ),
            params,
        ).scalar_one()
        compatibility_count = connection.execute(
            text(
                "SELECT count(*) FROM outbox.metric_definition_version_schema c "
                "JOIN outbox.metric_definition_version v "
                "ON v.id=c.metric_definition_version_id "
                "JOIN outbox.metric_definition d ON d.id=v.metric_definition_id "
                "WHERE d.event_type_id=:event_type_id"
            ),
            params,
        ).scalar_one()
        chain_count = connection.execute(
            text(
                "SELECT count(*) FROM outbox.processing_chain "
                "WHERE event_type_id=:event_type_id"
            ),
            params,
        ).scalar_one()
        plan_count = connection.execute(
            text(
                "SELECT count(*) FROM outbox.processing_plan p "
                "JOIN outbox.processing_chain c ON c.id=p.processing_chain_id "
                "WHERE c.event_type_id=:event_type_id"
            ),
            params,
        ).scalar_one()
    return (
        int(definition_count),
        int(version_count),
        int(compatibility_count),
        int(chain_count),
        int(plan_count),
    )


def _cleanup(project_id: int, event_type_id: int) -> None:
    with engine.begin() as connection:
        params = {"event_type_id": event_type_id, "project_id": project_id}
        connection.execute(
            text(
                "DELETE FROM outbox.metric_definition_version_schema WHERE "
                "metric_definition_version_id IN (SELECT v.id FROM "
                "outbox.metric_definition_version v JOIN outbox.metric_definition d "
                "ON d.id=v.metric_definition_id WHERE d.event_type_id=:event_type_id)"
            ),
            params,
        )
        connection.execute(
            text(
                "DELETE FROM outbox.metric_definition_version WHERE "
                "metric_definition_id IN (SELECT id FROM outbox.metric_definition "
                "WHERE event_type_id=:event_type_id)"
            ),
            params,
        )
        connection.execute(
            text(
                "DELETE FROM outbox.metric_definition "
                "WHERE event_type_id=:event_type_id"
            ),
            params,
        )
        connection.execute(
            text(
                "DELETE FROM outbox.schema_definition "
                "WHERE event_type_id=:event_type_id"
            ),
            params,
        )
        connection.execute(
            text("DELETE FROM outbox.event_type WHERE id=:event_type_id"), params
        )
        connection.execute(
            text("DELETE FROM outbox.project WHERE id=:project_id"), params
        )


def test_create_and_identical_replay_persist_one_exact_triplet_only() -> None:
    project, event_type, schema = _fixture_graph("builder-create")
    try:
        with SessionLocal() as session:
            service = _service(session)
            first = _create(service, event_type.id, schema.id)
            first_ids = (
                first.metric_definition.id,
                first.metric_definition_version.id,
                first.compatibility.id,
            )
            replay = _create(service, event_type.id, schema.id)
            replay_ids = (
                replay.metric_definition.id,
                replay.metric_definition_version.id,
                replay.compatibility.id,
            )
            replay_schema_id = replay.schema_definition.id

        assert first.created is True
        assert replay.created is False
        assert replay_ids == first_ids
        assert replay_schema_id == schema.id
        assert _counts(event_type.id) == (1, 1, 1, 0, 0)

        with engine.connect() as connection:
            exact_schema_id = connection.execute(
                text(
                    "SELECT c.schema_definition_id "
                    "FROM outbox.metric_definition_version_schema c "
                    "JOIN outbox.metric_definition_version v "
                    "ON v.id=c.metric_definition_version_id "
                    "JOIN outbox.metric_definition d "
                    "ON d.id=v.metric_definition_id "
                    "WHERE d.event_type_id=:event_type_id"
                ),
                {"event_type_id": event_type.id},
            ).scalar_one()
        assert exact_schema_id == schema.id
    finally:
        _cleanup(project.id, event_type.id)


@pytest.mark.parametrize(
    ("attribute", "repository_type", "message"),
    [
        (
            "metric_definition_repository",
            _PostFlushDefinitionFailure,
            "failure after definition flush",
        ),
        (
            "metric_definition_version_repository",
            _PostFlushVersionFailure,
            "failure after version flush",
        ),
        (
            "compatibility_repository",
            _PostFlushCompatibilityFailure,
            "failure after compatibility flush",
        ),
    ],
)
def test_post_flush_failure_rolls_back_and_session_recovers(
    attribute: str,
    repository_type,
    message: str,
) -> None:
    project, event_type, schema = _fixture_graph("builder-rollback")
    try:
        with SessionLocal() as session:
            service = _service(session)
            setattr(service, attribute, repository_type(session))

            with pytest.raises(RuntimeError, match=message):
                _create(service, event_type.id, schema.id)

            assert session.in_transaction() is False
            assert _counts(event_type.id) == (0, 0, 0, 0, 0)

            recovered = _create(
                _service(session),
                event_type.id,
                schema.id,
            )
            assert recovered.created is True

        assert _counts(event_type.id) == (1, 1, 1, 0, 0)
    finally:
        _cleanup(project.id, event_type.id)


def test_compilation_failure_precedes_writes_and_session_recovers() -> None:
    project, event_type, schema = _fixture_graph("builder-compile-rollback")
    try:
        with SessionLocal() as session:
            service = _service(session)
            service.metric_yaml_service.compile = Mock(
                side_effect=RuntimeError("compiler interrupted")
            )

            with pytest.raises(RuntimeError, match="compiler interrupted"):
                _create(service, event_type.id, schema.id)

            assert session.in_transaction() is False
            assert _counts(event_type.id) == (0, 0, 0, 0, 0)

            recovered = _create(
                _service(session),
                event_type.id,
                schema.id,
            )
            assert recovered.created is True

        assert _counts(event_type.id) == (1, 1, 1, 0, 0)
    finally:
        _cleanup(project.id, event_type.id)


def test_same_metric_code_is_allowed_in_another_event_type_scope() -> None:
    first_project, first_event_type, first_schema = _fixture_graph(
        "builder-scope-first"
    )
    second_project, second_event_type, second_schema = _fixture_graph(
        "builder-scope-second"
    )
    try:
        with SessionLocal() as session:
            first = _create(
                _service(session),
                first_event_type.id,
                first_schema.id,
            )
            second = _create(
                _service(session),
                second_event_type.id,
                second_schema.id,
            )
            definition_ids = (
                first.metric_definition.id,
                second.metric_definition.id,
            )

        assert definition_ids[0] != definition_ids[1]
        assert _counts(first_event_type.id) == (1, 1, 1, 0, 0)
        assert _counts(second_event_type.id) == (1, 1, 1, 0, 0)
    finally:
        _cleanup(first_project.id, first_event_type.id)
        _cleanup(second_project.id, second_event_type.id)


def test_two_identical_concurrent_creations_converge_on_one_triplet() -> None:
    project, event_type, schema = _fixture_graph("builder-identical")
    barrier = Barrier(2)

    def create() -> tuple[int, int, int, bool]:
        with SessionLocal() as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            service = _service(session)
            barrier.wait(timeout=10)
            result = _create(service, event_type.id, schema.id)
            return (
                result.metric_definition.id,
                result.metric_definition_version.id,
                result.compatibility.id,
                result.created,
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create), executor.submit(create)]
            results = [future.result(timeout=20) for future in futures]

        assert results[0][:3] == results[1][:3]
        assert sorted(result[3] for result in results) == [False, True]
        assert _counts(event_type.id) == (1, 1, 1, 0, 0)
    finally:
        _cleanup(project.id, event_type.id)


def test_two_conflicting_concurrent_creations_leave_one_winner() -> None:
    project, event_type, schema = _fixture_graph("builder-conflict")
    barrier = Barrier(2)

    def create(name: str):
        with SessionLocal() as session:
            service = _service(session)
            barrier.wait(timeout=10)
            try:
                result = _create(
                    service,
                    event_type.id,
                    schema.id,
                    name=name,
                )
                return ("created", result.metric_definition.id)
            except MetricBuilderAlreadyExistsError as exc:
                return ("conflict", exc.public_message())

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(create, "First meaning"),
                executor.submit(create, "Second meaning"),
            ]
            results = [future.result(timeout=20) for future in futures]

        assert sorted(result[0] for result in results) == ["conflict", "created"]
        assert _counts(event_type.id) == (1, 1, 1, 0, 0)
    finally:
        _cleanup(project.id, event_type.id)


def test_concurrent_normalized_name_collision_leaves_one_identity() -> None:
    project, event_type, schema = _fixture_graph("builder-name")
    barrier = Barrier(2)

    def create(code: str):
        with SessionLocal() as session:
            service = _service(session)
            barrier.wait(timeout=10)
            try:
                result = _create(
                    service,
                    event_type.id,
                    schema.id,
                    code=code,
                    name=code,
                )
                return ("created", result.prometheus_metric_name)
            except MetricBuilderNameCollisionError as exc:
                return ("conflict", exc.public_message())

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(create, "sales-total"),
                executor.submit(create, "sales_total"),
            ]
            results = [future.result(timeout=20) for future in futures]

        assert sorted(result[0] for result in results) == ["conflict", "created"]
        assert _counts(event_type.id) == (1, 1, 1, 0, 0)
    finally:
        _cleanup(project.id, event_type.id)
