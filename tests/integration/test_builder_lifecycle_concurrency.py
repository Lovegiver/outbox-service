"""PostgreSQL proofs for BDD-016C runtime isolation and concurrency."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.container.service_factory import ServiceFactory
from app.database import SessionLocal, engine
from app.services.metric_yaml_service import MetricYamlService
from app.services.processing_chain_errors import (
    ProcessingChainPrometheusCollisionError,
)
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
    RouteDefinitionRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.object_factory import ObjectFactory


def _compiled(code: str, *, negative: bool = False) -> dict:
    value_path = "$.amount" if negative else ""
    return {
        "compiler_version": "1.1",
        "yaml_version": "1.0",
        "observations": [
            {
                "metric_code": code,
                "transform": "identity" if negative else "constant",
                "value": {
                    "path": value_path,
                    "json_type": "number" if negative else "constant",
                    "required": True,
                    "nullable": False,
                    "iterator_path": None,
                },
                "labels": [],
            }
        ],
    }


def _seed_runtime_graph(
    *,
    event_count: int,
    plan_codes: tuple[str, ...],
    negative_plan: int | None = None,
):
    suffix = uuid4().hex
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"bdd-016c-{suffix}"))
        event_type = factory.event_type(
            EventTypeRecord(
                project=project,
                code=f"bdd.016c.{suffix}",
                name="BDD-016C concurrent runtime",
            )
        )
        schema = factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema={
                    "type": "object",
                    "properties": {"amount": {"type": "number"}},
                    "required": ["amount"],
                },
                json_version_internal="1.0",
            )
        )
        factory.route_definition(
            RouteDefinitionRecord(
                event_type=event_type,
                routing_key="all",
                destination_url="https://local.test/bdd-016c",
            )
        )
        chain = factory.processing_chain(
            ProcessingChainRecord(
                event_type=event_type,
                schema_definition=schema,
                status="ACTIVE",
                is_active=True,
            )
        )
        for position, code in enumerate(plan_codes):
            definition = factory.metric_definition(
                MetricDefinitionRecord(event_type=event_type, code=code, name=code)
            )
            version = factory.metric_definition_version(
                MetricDefinitionVersionRecord(metric_definition=definition)
            )
            factory.metric_definition_version_schema(
                MetricDefinitionVersionSchemaRecord(version, schema)
            )
            factory.processing_plan(
                ProcessingPlanRecord(
                    processing_chain=chain,
                    metric_definition=definition,
                    metric_definition_version=version,
                    position=position,
                    compiled_plan_json=_compiled(
                        code,
                        negative=negative_plan == position,
                    ),
                )
            )
        events = [
            factory.event(
                EventRecord(
                    event_type=event_type,
                    schema_definition=schema,
                    json_version_internal="1.0",
                    payload={"amount": -1 if negative_plan is not None else 1},
                    correlation_id=f"bdd-016c-{suffix}-{index}",
                )
            )
            for index in range(event_count)
        ]
    with SessionLocal() as session:
        route_received_events(session)
        session.commit()
    return project, event_type, schema, chain, events


def _run_two_metric_workers(
    *,
    require_distinct_first_acquisitions: bool = True,
) -> tuple[list[int], list[int]]:
    start = Barrier(2)
    first_locks = Barrier(2)

    def worker() -> list[int]:
        execution_ids: list[int] = []
        with SessionLocal() as session:
            service = ServiceFactory.create_metric_plan_execution_service(
                session,
                retry_delay=lambda _attempt: 0,
            )
            start.wait(timeout=10)
            first = service.execute_next()
            if first is None:
                session.rollback()
                return execution_ids
            execution_ids.append(first.execution_id)
            if require_distinct_first_acquisitions:
                first_locks.wait(timeout=10)
            session.commit()
            while True:
                result = service.execute_next()
                if result is None:
                    session.rollback()
                    break
                execution_ids.append(result.execution_id)
                session.commit()
        return execution_ids

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker), executor.submit(worker)]
        return tuple(future.result(timeout=60) for future in futures)  # type: ignore[return-value]


def _cleanup_project(project_id: int) -> None:
    params = {"project_id": project_id}
    statements = (
        "DELETE FROM outbox.metric_state WHERE project_id=:project_id",
        (
            "DELETE FROM outbox.metric_checkpoint WHERE checkpoint_name LIKE "
            "'prometheus_metric_state:' || :project_id || ':%'"
        ),
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
            "(SELECT pc.id FROM outbox.processing_chain pc JOIN outbox.event_type et "
            "ON et.id=pc.event_type_id WHERE et.project_id=:project_id)"
        ),
        (
            "DELETE FROM outbox.processing_chain WHERE event_type_id IN "
            "(SELECT id FROM outbox.event_type WHERE project_id=:project_id)"
        ),
        (
            "DELETE FROM outbox.metric_definition_version_schema WHERE "
            "metric_definition_version_id IN (SELECT mdv.id FROM "
            "outbox.metric_definition_version mdv JOIN outbox.metric_definition md "
            "ON md.id=mdv.metric_definition_id JOIN outbox.event_type et "
            "ON et.id=md.event_type_id WHERE et.project_id=:project_id)"
        ),
        (
            "DELETE FROM outbox.metric_definition_version WHERE "
            "metric_definition_id IN (SELECT md.id FROM "
            "outbox.metric_definition md JOIN outbox.event_type et "
            "ON et.id=md.event_type_id WHERE et.project_id=:project_id)"
        ),
        (
            "DELETE FROM outbox.metric_definition WHERE event_type_id IN "
            "(SELECT id FROM outbox.event_type WHERE project_id=:project_id)"
        ),
        (
            "DELETE FROM outbox.route_definition WHERE event_type_id IN "
            "(SELECT id FROM outbox.event_type WHERE project_id=:project_id)"
        ),
        (
            "DELETE FROM outbox.schema_definition WHERE event_type_id IN "
            "(SELECT id FROM outbox.event_type WHERE project_id=:project_id)"
        ),
        "DELETE FROM outbox.event_type WHERE project_id=:project_id",
        "DELETE FROM outbox.project WHERE id=:project_id",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement), params)


def _counts(project_id: int) -> dict[str, int]:
    with engine.connect() as connection:
        return {
            key: int(
                connection.execute(
                    text(statement), {"project_id": project_id}
                ).scalar_one()
            )
            for key, statement in {
                "events": "SELECT COUNT(*) FROM outbox.event WHERE project_id=:project_id",
                "executions": "SELECT COUNT(*) FROM outbox.metric_plan_execution mpe "
                "JOIN outbox.event e ON e.id=mpe.event_id WHERE e.project_id=:project_id",
                "terminal": "SELECT COUNT(*) FROM outbox.metric_plan_execution mpe "
                "JOIN outbox.event e ON e.id=mpe.event_id WHERE e.project_id=:project_id "
                "AND mpe.status IN ('SUCCEEDED','FAILED_PERMANENT')",
                "observations": "SELECT COUNT(*) FROM outbox.analytical_observation "
                "WHERE project_id=:project_id",
                "deliveries": "SELECT COUNT(*) FROM outbox.event_delivery ed JOIN "
                "outbox.event e ON e.id=ed.event_id WHERE e.project_id=:project_id",
                "pending": "SELECT COUNT(*) FROM outbox.metric_plan_execution mpe "
                "JOIN outbox.event e ON e.id=mpe.event_id WHERE e.project_id=:project_id "
                "AND mpe.status IN ('PENDING','RUNNING','RETRYABLE')",
            }.items()
        }


def test_two_metric_workers_drain_30_events_and_150_plans_once() -> None:
    project, event_type, _, _, _ = _seed_runtime_graph(
        event_count=30,
        plan_codes=tuple(f"worker_counter_{index}" for index in range(5)),
    )
    try:
        worker_results = _run_two_metric_workers()
        all_execution_ids = [item for worker in worker_results for item in worker]
        assert all(worker for worker in worker_results)
        assert len(all_execution_ids) == 150
        assert len(set(all_execution_ids)) == 150

        with SessionLocal() as session:
            aggregation = ServiceFactory.create_metric_state_aggregation_service(
                session
            )
            assert aggregation.aggregate_stream(project.id, event_type.id, 1000) == 150
            session.commit()

        assert _counts(project.id) == {
            "events": 30,
            "executions": 150,
            "terminal": 150,
            "observations": 150,
            "deliveries": 30,
            "pending": 0,
        }
        with engine.connect() as connection:
            states = (
                connection.execute(
                    text(
                        "SELECT metric_code, value FROM outbox.metric_state "
                        "WHERE project_id=:project_id ORDER BY metric_code"
                    ),
                    {"project_id": project.id},
                )
                .mappings()
                .all()
            )
            checkpoint = connection.execute(
                text(
                    "SELECT last_processed_observation_id FROM outbox.metric_checkpoint "
                    "WHERE checkpoint_name=:name"
                ),
                {"name": f"prometheus_metric_state:{project.id}:{event_type.id}"},
            ).scalar_one()
            last_observation = connection.execute(
                text(
                    "SELECT MAX(id) FROM outbox.analytical_observation "
                    "WHERE project_id=:project_id"
                ),
                {"project_id": project.id},
            ).scalar_one()
        assert [row["value"] for row in states] == [30.0] * 5
        assert checkpoint == last_observation

        assert _run_empty_metric_cycle() == ()
        with SessionLocal() as session:
            aggregation = ServiceFactory.create_metric_state_aggregation_service(
                session
            )
            assert aggregation.aggregate_stream(project.id, event_type.id, 1000) == 0
            session.commit()
        with SessionLocal() as session:
            route_received_events(session)
            session.commit()
        assert _counts(project.id)["deliveries"] == 30
    finally:
        _cleanup_project(project.id)


def _run_empty_metric_cycle() -> tuple:
    with SessionLocal() as session:
        service = ServiceFactory.create_metric_plan_execution_service(
            session,
            retry_delay=lambda _attempt: 0,
        )
        assert service.execute_next() is None
        session.rollback()
    return ()


def test_permanent_plan_is_isolated_under_two_metric_workers() -> None:
    project, _event_type, _, _, events = _seed_runtime_graph(
        event_count=1,
        plan_codes=("valid_a", "invalid_negative", "valid_c"),
        negative_plan=1,
    )
    try:
        worker_results = _run_two_metric_workers(
            require_distinct_first_acquisitions=False
        )
        assert sum(len(worker) for worker in worker_results) == 3
        with engine.connect() as connection:
            executions = (
                connection.execute(
                    text(
                        "SELECT pp.position, mpe.status, mpe.attempt_count, "
                        "mpe.is_retryable FROM outbox.metric_plan_execution mpe "
                        "JOIN outbox.processing_plan pp ON pp.id=mpe.processing_plan_id "
                        "WHERE mpe.event_id=:event_id ORDER BY pp.position"
                    ),
                    {"event_id": events[0].id},
                )
                .mappings()
                .all()
            )
            parent_status = connection.execute(
                text(
                    "SELECT status FROM outbox.metric_processing_execution "
                    "WHERE event_id=:event_id"
                ),
                {"event_id": events[0].id},
            ).scalar_one()
        assert [row["status"] for row in executions] == [
            "SUCCEEDED",
            "FAILED_PERMANENT",
            "SUCCEEDED",
        ]
        assert [row["attempt_count"] for row in executions] == [1, 1, 1]
        assert executions[1]["is_retryable"] is False
        assert parent_status == "COMPLETED_WITH_ERRORS"
        counts = _counts(project.id)
        assert counts["observations"] == 2
        assert counts["deliveries"] == 1
        assert counts["pending"] == 0
        assert _run_empty_metric_cycle() == ()
        assert _counts(project.id)["deliveries"] == 1
    finally:
        _cleanup_project(project.id)


def test_structurally_identical_schemas_remain_isolated_by_event_type() -> None:
    suffix = uuid4().hex
    schema_json = {"type": "object", "properties": {"amount": {"type": "number"}}}
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"bdd-016c-isolation-{suffix}"))
        scopes = []
        for scope_name in ("a", "b"):
            event_type = factory.event_type(
                EventTypeRecord(
                    project=project,
                    code=f"identical.{scope_name}.{suffix}",
                    name=f"Identical {scope_name}",
                )
            )
            schema = factory.schema_definition(
                SchemaDefinitionRecord(
                    event_type=event_type,
                    json_schema=schema_json,
                    json_version_internal="1.0",
                )
            )
            definition = factory.metric_definition(
                MetricDefinitionRecord(
                    event_type=event_type,
                    code="shared_total",
                    name="Shared total",
                )
            )
            version = factory.metric_definition_version(
                MetricDefinitionVersionRecord(metric_definition=definition)
            )
            compatibility = factory.metric_definition_version_schema(
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
            factory.processing_plan(
                ProcessingPlanRecord(
                    processing_chain=chain,
                    metric_definition=definition,
                    metric_definition_version=version,
                    compiled_plan_json=_compiled("shared_total"),
                )
            )
            event = factory.event(
                EventRecord(
                    event_type=event_type,
                    schema_definition=schema,
                    json_version_internal="1.0",
                    payload={"amount": 1},
                )
            )
            scopes.append((event_type, schema, compatibility, chain, event))

    try:
        with SessionLocal() as session:
            route_received_events(session)
            session.commit()
        with SessionLocal() as session:
            service = ServiceFactory.create_metric_plan_execution_service(
                session,
                retry_delay=lambda _attempt: 0,
            )
            while service.execute_next() is not None:
                session.commit()
            session.rollback()
        with SessionLocal() as session:
            aggregator = ServiceFactory.create_metric_state_aggregation_service(session)
            for event_type, _, _, _, _ in scopes:
                assert aggregator.aggregate_stream(project.id, event_type.id, 100) == 1
                session.commit()
            document = ServiceFactory.create_prometheus_metric_state_service(
                session
            ).render_project(project.id)

        with engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        "SELECT ao.event_type_id, ao.processing_chain_id, e.schema_definition_id "
                        "FROM outbox.analytical_observation ao JOIN outbox.event e "
                        "ON e.id=ao.event_id WHERE ao.project_id=:project_id "
                        "ORDER BY ao.event_type_id"
                    ),
                    {"project_id": project.id},
                )
                .mappings()
                .all()
            )
            compatibility_pairs = connection.execute(
                text(
                    "SELECT md.event_type_id, mdvs.schema_definition_id FROM "
                    "outbox.metric_definition_version_schema mdvs JOIN "
                    "outbox.metric_definition_version mdv ON mdv.id="
                    "mdvs.metric_definition_version_id JOIN outbox.metric_definition md "
                    "ON md.id=mdv.metric_definition_id WHERE md.event_type_id = ANY(:ids)"
                ),
                {"ids": [scope[0].id for scope in scopes]},
            ).all()

        assert len(rows) == 2
        for row, (event_type, schema, _, chain, _) in zip(rows, scopes, strict=True):
            assert row == {
                "event_type_id": event_type.id,
                "processing_chain_id": chain.id,
                "schema_definition_id": schema.id,
            }
        assert set(compatibility_pairs) == {
            (scope[0].id, scope[1].id) for scope in scopes
        }
        assert document.count("ob1_shared_total{") == 2
        for event_type, _, _, _, _ in scopes:
            assert f'ob1_event_type="{event_type.code}"' in document
    finally:
        _cleanup_project(project.id)


COLLIDING_YAML = (
    ('version: "1.0"\nobservations:\n  - code: sales-total\n    transform: constant\n'),
    ('version: "1.0"\nobservations:\n  - code: sales_total\n    transform: constant\n'),
)


def _seed_collision_scope(*, include_second: bool):
    suffix = uuid4().hex
    schema_json = {"type": "object", "properties": {}}
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"bdd-016c-collision-{suffix}"))
        event_type = factory.event_type(
            EventTypeRecord(
                project=project,
                code=f"collision.{suffix}",
                name="Collision scope",
            )
        )
        schema = factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema=schema_json,
                json_version_internal="1.0",
            )
        )
        versions = []
        for index, yaml_content in enumerate(COLLIDING_YAML):
            if index == 1 and not include_second:
                break
            definition = factory.metric_definition(
                MetricDefinitionRecord(
                    event_type=event_type,
                    code=("sales-total" if index == 0 else "sales_total"),
                    name=f"Collision metric {index}",
                )
            )
            version = factory.metric_definition_version(
                MetricDefinitionVersionRecord(
                    metric_definition=definition,
                    yaml_content=yaml_content,
                )
            )
            factory.metric_definition_version_schema(
                MetricDefinitionVersionSchemaRecord(version, schema)
            )
            versions.append((definition, version))
    return project, event_type, schema, schema_json, versions


def test_rebuild_collision_preserves_existing_active_snapshot() -> None:
    project, event_type, schema, _, versions = _seed_collision_scope(
        include_second=False
    )
    try:
        with SessionLocal() as session:
            service = ServiceFactory.create_processing_chain_activation_service(session)
            active = service.rebuild_chain(event_type.id, schema.id)
            active = service.activate_chain(event_type.id, schema.id, active.id)
            active_id = active.id

        with engine.begin() as connection:
            factory = ObjectFactory(connection)
            definition = factory.metric_definition(
                MetricDefinitionRecord(
                    event_type=event_type,
                    code="sales_total",
                    name="Collision metric 1",
                )
            )
            version = factory.metric_definition_version(
                MetricDefinitionVersionRecord(
                    metric_definition=definition,
                    yaml_content=COLLIDING_YAML[1],
                )
            )
            factory.metric_definition_version_schema(
                MetricDefinitionVersionSchemaRecord(version, schema)
            )
            versions.append((definition, version))

        with SessionLocal() as session:
            service = ServiceFactory.create_processing_chain_activation_service(session)
            with pytest.raises(
                ProcessingChainPrometheusCollisionError,
                match="BUILDER_PROMETHEUS_NAME_COLLISION",
            ):
                service.rebuild_chain(event_type.id, schema.id)
            assert session.in_transaction() is False

        with engine.connect() as connection:
            chains = (
                connection.execute(
                    text(
                        "SELECT id, status, is_active FROM outbox.processing_chain "
                        "WHERE event_type_id=:event_type_id ORDER BY id"
                    ),
                    {"event_type_id": event_type.id},
                )
                .mappings()
                .all()
            )
        assert chains == [{"id": active_id, "status": "ACTIVE", "is_active": True}]
    finally:
        _cleanup_project(project.id)


def test_activation_revalidates_historical_draft_collision_under_lock() -> None:
    project, event_type, schema, schema_json, versions = _seed_collision_scope(
        include_second=True
    )
    try:
        compiled = [
            MetricYamlService().compile(yaml_content, schema_json).compiled_plan_json
            for yaml_content in COLLIDING_YAML
        ]
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
                    metric_definition=versions[0][0],
                    metric_definition_version=versions[0][1],
                    compiled_plan_json=compiled[0],
                )
            )
            candidate = factory.processing_chain(
                ProcessingChainRecord(
                    event_type=event_type,
                    schema_definition=schema,
                    version_number=2,
                    status="DRAFT",
                    is_active=False,
                )
            )
            for position, ((definition, version), plan) in enumerate(
                zip(versions, compiled, strict=True)
            ):
                factory.processing_plan(
                    ProcessingPlanRecord(
                        processing_chain=candidate,
                        metric_definition=definition,
                        metric_definition_version=version,
                        position=position,
                        compiled_plan_json=plan,
                    )
                )

        with SessionLocal() as session:
            service = ServiceFactory.create_processing_chain_activation_service(session)
            with pytest.raises(
                ProcessingChainPrometheusCollisionError,
                match="BUILDER_PROMETHEUS_NAME_COLLISION",
            ):
                service.activate_chain(event_type.id, schema.id, candidate.id)

        with engine.connect() as connection:
            rows = (
                connection.execute(
                    text(
                        "SELECT id, status, is_active FROM outbox.processing_chain "
                        "WHERE event_type_id=:event_type_id ORDER BY version_number"
                    ),
                    {"event_type_id": event_type.id},
                )
                .mappings()
                .all()
            )
        assert rows == [
            {"id": active.id, "status": "ACTIVE", "is_active": True},
            {"id": candidate.id, "status": "DRAFT", "is_active": False},
        ]
    finally:
        _cleanup_project(project.id)
