from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.container.service_factory import ServiceFactory
from app.core.metric_execution_status import MetricPlanExecutionStatus
from app.database import SessionLocal, engine
from app.repositories.metric_execution_repository import MetricExecutionRepository
from app.worker import route_received_events
from tests.domain.record import (
    EventRecord,
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


def _compiled() -> dict:
    return {
        "compiler_version": "1.0",
        "yaml_version": "1.0",
        "observations": [
            {
                "metric_code": "concurrent_total",
                "transform": "constant",
                "value": {
                    "path": "",
                    "json_type": "constant",
                    "required": True,
                    "iterator_path": None,
                },
                "labels": [],
            }
        ],
    }


def _committed_runtime_graph():
    suffix = uuid4().hex
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"metric-runtime-{suffix}"))
        event_type = factory.event_type(
            EventTypeRecord(
                project=project,
                code=f"metric.runtime.{suffix}",
                name="Metric runtime concurrency",
            )
        )
        schema = factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema={"type": "object"},
                json_version_internal="1",
            )
        )
        definition = factory.metric_definition(
            MetricDefinitionRecord(
                event_type=event_type,
                code="concurrent_total",
                name="Concurrent total",
            )
        )
        version = factory.metric_definition_version(
            MetricDefinitionVersionRecord(metric_definition=definition)
        )
        factory.metric_definition_version_schema(
            MetricDefinitionVersionSchemaRecord(version, schema)
        )
        chain = factory.processing_chain(
            ProcessingChainRecord(
                event_type=event_type,
                schema_definition=schema,
                status="ACTIVE",
                is_active=True,
            )
        )
        plan = factory.processing_plan(
            ProcessingPlanRecord(
                processing_chain=chain,
                metric_definition=definition,
                metric_definition_version=version,
                compiled_plan_json=_compiled(),
            )
        )
        event = factory.event(
            EventRecord(
                event_type=event_type,
                schema_definition=schema,
                json_version_internal=schema.json_version_internal,
            )
        )
    with SessionLocal() as session:
        route_received_events(session)
        session.commit()
    return project, event_type, definition, event, plan


def _cleanup(project_id: int, event_type_id: int) -> None:
    with engine.begin() as connection:
        for statement in (
            "DELETE FROM outbox.metric_state WHERE project_id=:project_id",
            "DELETE FROM outbox.analytical_observation WHERE project_id=:project_id",
            (
                "DELETE FROM outbox.metric_plan_execution WHERE event_id IN "
                "(SELECT id FROM outbox.event WHERE project_id=:project_id)"
            ),
            (
                "DELETE FROM outbox.metric_processing_execution WHERE event_id IN "
                "(SELECT id FROM outbox.event WHERE project_id=:project_id)"
            ),
            (
                "DELETE FROM outbox.event_delivery WHERE event_id IN "
                "(SELECT id FROM outbox.event WHERE project_id=:project_id)"
            ),
            "DELETE FROM outbox.event WHERE project_id=:project_id",
            (
                "DELETE FROM outbox.processing_plan WHERE processing_chain_id IN "
                "(SELECT id FROM outbox.processing_chain "
                "WHERE event_type_id=:event_type_id)"
            ),
            "DELETE FROM outbox.processing_chain WHERE event_type_id=:event_type_id",
            (
                "DELETE FROM outbox.metric_definition_version_schema "
                "WHERE schema_definition_id IN "
                "(SELECT id FROM outbox.schema_definition "
                "WHERE event_type_id=:event_type_id)"
            ),
            (
                "DELETE FROM outbox.metric_definition_version "
                "WHERE metric_definition_id IN "
                "(SELECT id FROM outbox.metric_definition "
                "WHERE event_type_id=:event_type_id)"
            ),
            "DELETE FROM outbox.metric_definition WHERE event_type_id=:event_type_id",
            "DELETE FROM outbox.schema_definition WHERE event_type_id=:event_type_id",
            "DELETE FROM outbox.event_type WHERE id=:event_type_id",
            "DELETE FROM outbox.project WHERE id=:project_id",
        ):
            connection.execute(
                text(statement),
                {"project_id": project_id, "event_type_id": event_type_id},
            )


def test_two_workers_execute_one_metric_plan_exactly_once() -> None:
    project, event_type, _, event, _ = _committed_runtime_graph()
    barrier = Barrier(2)

    def run_worker():
        with SessionLocal() as session:
            service = ServiceFactory.create_metric_plan_execution_service(
                session, retry_delay=lambda _attempt: 0
            )
            barrier.wait(timeout=10)
            result = service.execute_next()
            session.commit()
            return result

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [
                future.result(timeout=20)
                for future in [executor.submit(run_worker), executor.submit(run_worker)]
            ]

        assert sum(result is not None for result in results) == 1
        with engine.connect() as connection:
            execution = (
                connection.execute(
                    text(
                        "SELECT status, attempt_count "
                        "FROM outbox.metric_plan_execution "
                        "WHERE event_id=:event_id"
                    ),
                    {"event_id": event.id},
                )
                .mappings()
                .one()
            )
            observation_count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM outbox.analytical_observation "
                    "WHERE event_id=:event_id"
                ),
                {"event_id": event.id},
            ).scalar_one()
        assert execution == {"status": "SUCCEEDED", "attempt_count": 1}
        assert observation_count == 1
    finally:
        _cleanup(project.id, event_type.id)


def test_event_plan_uniqueness_is_enforced_by_postgresql() -> None:
    project, event_type, _, event, _ = _committed_runtime_graph()

    try:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO outbox.metric_plan_execution "
                        "(metric_processing_execution_id, event_id, "
                        "processing_chain_id, processing_plan_id, status, "
                        "attempt_count, is_retryable) "
                        "SELECT metric_processing_execution_id, event_id, "
                        "processing_chain_id, processing_plan_id, status, "
                        "attempt_count, is_retryable "
                        "FROM outbox.metric_plan_execution WHERE event_id=:event_id"
                    ),
                    {"event_id": event.id},
                )
    finally:
        _cleanup(project.id, event_type.id)


def test_runtime_observation_identity_is_enforced_by_postgresql() -> None:
    project, event_type, _, event, _ = _committed_runtime_graph()

    try:
        with SessionLocal() as session:
            service = ServiceFactory.create_metric_plan_execution_service(
                session, retry_delay=lambda _attempt: 0
            )
            assert service.execute_next() is not None
            session.commit()

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO outbox.analytical_observation "
                        "(project_id, event_type_id, event_id, "
                        "metric_definition_id, metric_definition_version_id, "
                        "processing_chain_id, processing_plan_id, "
                        "metric_plan_execution_id, observation_key, metric_code, "
                        "value, dimensions_json) "
                        "SELECT project_id, event_type_id, event_id, "
                        "metric_definition_id, metric_definition_version_id, "
                        "processing_chain_id, processing_plan_id, "
                        "metric_plan_execution_id, observation_key, metric_code, "
                        "value, dimensions_json "
                        "FROM outbox.analytical_observation WHERE event_id=:event_id"
                    ),
                    {"event_id": event.id},
                )

        with engine.connect() as connection:
            count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM outbox.analytical_observation "
                    "WHERE event_id=:event_id"
                ),
                {"event_id": event.id},
            ).scalar_one()
        assert count == 1
    finally:
        _cleanup(project.id, event_type.id)


def test_crash_before_commit_rolls_back_running_and_releases_execution() -> None:
    project, event_type, _, event, _ = _committed_runtime_graph()

    try:
        with SessionLocal() as interrupted_session:
            repository = MetricExecutionRepository(interrupted_session)
            locked = repository.lock_next_eligible(max_attempts=3)
            assert locked is not None
            locked.status = MetricPlanExecutionStatus.RUNNING
            locked.attempt_count += 1
            interrupted_session.flush()

            with engine.connect() as observer:
                visible = (
                    observer.execute(
                        text(
                            "SELECT status, attempt_count "
                            "FROM outbox.metric_plan_execution WHERE event_id=:event_id"
                        ),
                        {"event_id": event.id},
                    )
                    .mappings()
                    .one()
                )
            assert visible == {"status": "PENDING", "attempt_count": 0}

            with pytest.raises(RuntimeError, match="simulated worker interruption"):
                raise RuntimeError("simulated worker interruption")
            interrupted_session.rollback()

        with SessionLocal() as recovery_session:
            service = ServiceFactory.create_metric_plan_execution_service(
                recovery_session, retry_delay=lambda _attempt: 0
            )
            recovered = service.execute_next()
            recovery_session.commit()

        assert recovered is not None
        assert recovered.status == "SUCCEEDED"
        with engine.connect() as connection:
            execution = (
                connection.execute(
                    text(
                        "SELECT status, attempt_count "
                        "FROM outbox.metric_plan_execution WHERE event_id=:event_id"
                    ),
                    {"event_id": event.id},
                )
                .mappings()
                .one()
            )
            assert (
                connection.execute(
                    text(
                        "SELECT COUNT(*) FROM outbox.analytical_observation "
                        "WHERE event_id=:event_id"
                    ),
                    {"event_id": event.id},
                ).scalar_one()
                == 1
            )
            delivery_count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM outbox.event_delivery "
                    "WHERE event_id=:event_id"
                ),
                {"event_id": event.id},
            ).scalar_one()
        assert execution == {"status": "SUCCEEDED", "attempt_count": 1}
        assert delivery_count == 0
    finally:
        _cleanup(project.id, event_type.id)
