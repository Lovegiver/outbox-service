from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.repositories.analytical_observation_repository import (
    AnalyticalObservationRepository,
)
from app.services.metrics_extraction_service import MetricsExtractionService
from app.worker import (
    aggregate_prometheus_metric_state,
    process_metric_plan_executions,
    route_received_events,
)
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

SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number"},
        "country": {"type": "string"},
    },
    "required": ["amount"],
}


def _compiled(
    code: str,
    *,
    transform: str = "constant",
    path: str = "",
    required: bool = True,
    labels: list[dict] | None = None,
) -> dict:
    return {
        "compiler_version": "1.0",
        "yaml_version": "1.0",
        "observations": [
            {
                "metric_code": code,
                "transform": transform,
                "value": {
                    "path": path,
                    "json_type": "constant" if transform == "constant" else "number",
                    "required": required,
                    "iterator_path": None,
                },
                "labels": labels or [],
            }
        ],
    }


def _seed_runtime(
    factory: ObjectFactory,
    *,
    compiled_plans: list[dict],
    payload: dict | None = None,
    with_route: bool = True,
):
    project = factory.project(ProjectRecord(name="runtime-project"))
    event_type = factory.event_type(
        EventTypeRecord(project=project, code="order.created", name="Order created")
    )
    schema = factory.schema_definition(
        SchemaDefinitionRecord(event_type=event_type, json_schema=SCHEMA)
    )
    chain = factory.processing_chain(
        ProcessingChainRecord(
            event_type=event_type,
            schema_definition=schema,
            status="ACTIVE",
            is_active=True,
        )
    )
    plans = []
    for position, compiled in enumerate(compiled_plans):
        definition = factory.metric_definition(
            MetricDefinitionRecord(
                event_type=event_type,
                code=f"definition_{position}",
                name=f"Definition {position}",
            )
        )
        version = factory.metric_definition_version(
            MetricDefinitionVersionRecord(metric_definition=definition)
        )
        factory.metric_definition_version_schema(
            MetricDefinitionVersionSchemaRecord(
                metric_definition_version=version,
                schema_definition=schema,
            )
        )
        plans.append(
            factory.processing_plan(
                ProcessingPlanRecord(
                    processing_chain=chain,
                    metric_definition=definition,
                    metric_definition_version=version,
                    position=position,
                    compiled_plan_json=compiled,
                )
            )
        )
    if with_route:
        factory.route_definition(
            RouteDefinitionRecord(event_type=event_type, routing_key="all")
        )
    event = factory.event(
        EventRecord(
            event_type=event_type,
            schema_definition=schema,
            payload=payload or {"amount": 12},
        )
    )
    return project, event_type, schema, chain, plans, event


def _count(connection: Connection, table: str, where: str, **params) -> int:
    return int(
        connection.execute(
            text(f"SELECT COUNT(*) FROM outbox.{table} WHERE {where}"), params
        ).scalar_one()
    )


def test_runtime_materializes_routes_executes_and_replays_idempotently(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
) -> None:
    _, _, _, chain, plans, event = _seed_runtime(
        factory,
        compiled_plans=[_compiled("orders_total")],
    )

    route_received_events(db_session)
    assert (
        _count(
            db_connection, "metric_processing_execution", "event_id=:id", id=event.id
        )
        == 1
    )
    assert (
        _count(db_connection, "metric_plan_execution", "event_id=:id", id=event.id) == 1
    )
    assert _count(db_connection, "event_delivery", "event_id=:id", id=event.id) == 1

    first = process_metric_plan_executions(db_session)
    second = process_metric_plan_executions(db_session)

    assert first[0].status == "SUCCEEDED"
    assert second == ()
    assert (
        _count(db_connection, "analytical_observation", "event_id=:id", id=event.id)
        == 1
    )
    row = (
        db_connection.execute(
            text(
                "SELECT processing_chain_id, processing_plan_id, observation_key "
                "FROM outbox.analytical_observation WHERE event_id=:id"
            ),
            {"id": event.id},
        )
        .mappings()
        .one()
    )
    assert row["processing_chain_id"] == chain.id
    assert row["processing_plan_id"] == plans[0].id
    assert row["observation_key"] == "observation:0:occurrence:0"


def test_real_downstream_pipeline_coalesces_internal_counter_partitions(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
) -> None:
    optional_country = {
        "name": "country",
        "kind": "path",
        "path": "$.missing_country",
        "json_type": "string",
        "required": False,
        "iterator_path": None,
    }
    empty_country = {
        "name": "country",
        "kind": "path",
        "path": "$.country",
        "json_type": "string",
        "required": True,
        "iterator_path": None,
    }
    project, _, _, _, _, event = _seed_runtime(
        factory,
        compiled_plans=[
            _compiled("coalesced_total", labels=[optional_country]),
            _compiled("coalesced_total"),
            _compiled("coalesced_total", labels=[empty_country]),
        ],
        payload={"amount": 12, "country": ""},
    )

    route_received_events(db_session)
    process_metric_plan_executions(db_session)
    aggregate_prometheus_metric_state(db_session)

    states = (
        db_connection.execute(
            text(
                "SELECT labels_json, value FROM outbox.metric_state "
                "WHERE project_id=:project_id ORDER BY labels_hash"
            ),
            {"project_id": project.id},
        )
        .mappings()
        .all()
    )
    document = ServiceFactory.create_prometheus_metric_state_service(
        db_session
    ).render_project(project.id)

    assert [row["value"] for row in states] == [1.0, 1.0, 1.0]
    assert {} in [row["labels_json"] for row in states]
    assert {"country": None} in [row["labels_json"] for row in states]
    assert {"country": ""} in [row["labels_json"] for row in states]
    assert document.count("ob1_coalesced_total{") == 1
    assert document.endswith("} 3\n")
    assert (
        _count(db_connection, "analytical_observation", "event_id=:id", id=event.id)
        == 3
    )


def test_each_plan_is_atomic_and_routing_survives_metric_failure(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
) -> None:
    _, _, _, _, _, event = _seed_runtime(
        factory,
        compiled_plans=[
            _compiled("first_total"),
            _compiled("broken_total", transform="unknown", path="$.amount"),
            _compiled("third_total"),
        ],
    )

    route_received_events(db_session)
    results = process_metric_plan_executions(db_session)

    assert [result.status for result in results] == [
        "SUCCEEDED",
        "FAILED_PERMANENT",
        "SUCCEEDED",
    ]
    metric_codes = (
        db_connection.execute(
            text(
                "SELECT metric_code FROM outbox.analytical_observation "
                "WHERE event_id=:id ORDER BY metric_code"
            ),
            {"id": event.id},
        )
        .scalars()
        .all()
    )
    assert list(metric_codes) == ["first_total", "third_total"]
    assert _count(db_connection, "event_delivery", "event_id=:id", id=event.id) == 1


def test_negative_counter_fails_one_plan_before_observation_or_metric_state(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
) -> None:
    project, _, _, _, _, event = _seed_runtime(
        factory,
        compiled_plans=[
            _compiled("positive_before_total"),
            _compiled("negative_total", transform="identity", path="$.amount"),
            _compiled("positive_after_total"),
        ],
        payload={"amount": -5},
    )

    route_received_events(db_session)
    first_results = process_metric_plan_executions(db_session)
    aggregate_prometheus_metric_state(db_session)
    delivery_count = _count(
        db_connection, "event_delivery", "event_id=:id", id=event.id
    )
    second_results = process_metric_plan_executions(db_session)

    execution_rows = (
        db_connection.execute(
            text(
                "SELECT status, attempt_count, last_error, is_retryable "
                "FROM outbox.metric_plan_execution WHERE event_id=:event_id "
                "ORDER BY processing_plan_id"
            ),
            {"event_id": event.id},
        )
        .mappings()
        .all()
    )
    observation_codes = list(
        db_connection.execute(
            text(
                "SELECT metric_code FROM outbox.analytical_observation "
                "WHERE event_id=:event_id ORDER BY metric_code"
            ),
            {"event_id": event.id},
        ).scalars()
    )
    state_codes = list(
        db_connection.execute(
            text(
                "SELECT metric_code FROM outbox.metric_state "
                "WHERE project_id=:project_id ORDER BY metric_code"
            ),
            {"project_id": project.id},
        ).scalars()
    )
    parent_status = db_connection.execute(
        text(
            "SELECT status FROM outbox.metric_processing_execution "
            "WHERE event_id=:event_id"
        ),
        {"event_id": event.id},
    ).scalar_one()

    assert [result.status for result in first_results] == [
        "SUCCEEDED",
        "FAILED_PERMANENT",
        "SUCCEEDED",
    ]
    assert [row["status"] for row in execution_rows] == [
        "SUCCEEDED",
        "FAILED_PERMANENT",
        "SUCCEEDED",
    ]
    assert execution_rows[1]["last_error"].startswith("COUNTER_VALUE_NEGATIVE:")
    assert execution_rows[1]["is_retryable"] is False
    assert [row["attempt_count"] for row in execution_rows] == [1, 1, 1]
    assert observation_codes == ["positive_after_total", "positive_before_total"]
    assert state_codes == ["positive_after_total", "positive_before_total"]
    assert parent_status == "COMPLETED_WITH_ERRORS"
    assert second_results == ()
    assert delivery_count == 1
    assert _count(db_connection, "event_delivery", "event_id=:id", id=event.id) == 1


def test_parent_execution_distinguishes_processing_from_materialized_and_success(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
    monkeypatch,
) -> None:
    _, _, _, _, _, event = _seed_runtime(
        factory,
        compiled_plans=[_compiled("lifecycle_total")],
    )
    route_received_events(db_session)
    assert (
        db_connection.execute(
            text(
                "SELECT status FROM outbox.metric_processing_execution "
                "WHERE event_id=:event_id"
            ),
            {"event_id": event.id},
        ).scalar_one()
        == "MATERIALIZED"
    )
    original = MetricsExtractionService.extract_for_plan

    def observe_processing(service, **kwargs):
        assert (
            db_session.execute(
                text(
                    "SELECT status FROM outbox.metric_processing_execution "
                    "WHERE event_id=:event_id"
                ),
                {"event_id": event.id},
            ).scalar_one()
            == "PROCESSING"
        )
        return original(service, **kwargs)

    monkeypatch.setattr(
        MetricsExtractionService,
        "extract_for_plan",
        observe_processing,
    )

    process_metric_plan_executions(db_session)

    assert (
        db_connection.execute(
            text(
                "SELECT status FROM outbox.metric_processing_execution "
                "WHERE event_id=:event_id"
            ),
            {"event_id": event.id},
        ).scalar_one()
        == "SUCCEEDED"
    )


def test_first_materialized_snapshot_is_frozen_when_active_chain_changes(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
) -> None:
    _, event_type, schema, first_chain, first_plans, event = _seed_runtime(
        factory,
        compiled_plans=[_compiled("original_total")],
        with_route=False,
    )
    route_received_events(db_session)
    db_connection.execute(
        text(
            "UPDATE outbox.processing_chain SET is_active=false, status='RETIRED' "
            "WHERE id=:id"
        ),
        {"id": first_chain.id},
    )
    replacement = factory.processing_chain(
        ProcessingChainRecord(
            event_type=event_type,
            schema_definition=schema,
            version_number=2,
            status="ACTIVE",
            is_active=True,
        )
    )
    definition = first_plans[0].metric_definition
    version = first_plans[0].metric_definition_version
    factory.processing_plan(
        ProcessingPlanRecord(
            processing_chain=replacement,
            metric_definition=definition,
            metric_definition_version=version,
            compiled_plan_json=_compiled("replacement_total"),
        )
    )

    process_metric_plan_executions(db_session)

    row = (
        db_connection.execute(
            text(
                "SELECT processing_chain_id, metric_code "
                "FROM outbox.analytical_observation WHERE event_id=:id"
            ),
            {"id": event.id},
        )
        .mappings()
        .one()
    )
    assert row == {
        "processing_chain_id": first_chain.id,
        "metric_code": "original_total",
    }


def test_no_active_chain_is_a_normal_noop_and_routing_continues(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
) -> None:
    project = factory.project(ProjectRecord(name="no-metrics"))
    event_type = factory.event_type(
        EventTypeRecord(project=project, code="plain.event", name="Plain")
    )
    schema = factory.schema_definition(SchemaDefinitionRecord(event_type=event_type))
    factory.route_definition(
        RouteDefinitionRecord(event_type=event_type, routing_key="all")
    )
    event = factory.event(EventRecord(event_type=event_type, schema_definition=schema))

    route_received_events(db_session)

    assert (
        _count(
            db_connection, "metric_processing_execution", "event_id=:id", id=event.id
        )
        == 0
    )
    assert _count(db_connection, "event_delivery", "event_id=:id", id=event.id) == 1


def test_materialization_failure_is_isolated_per_event(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
    monkeypatch,
) -> None:
    _, event_type, schema, _, _, first_event = _seed_runtime(
        factory,
        compiled_plans=[_compiled("isolated_total")],
    )
    second_event = factory.event(
        EventRecord(
            event_type=event_type, schema_definition=schema, payload={"amount": 5}
        )
    )
    delegate = ServiceFactory.create_metric_execution_materialization_service(
        db_session
    )

    class FailFirstMaterialization:
        def materialize_for_event(self, event):
            if event.id == first_event.id:
                raise RuntimeError("simulated materialization failure")
            return delegate.materialize_for_event(event)

    monkeypatch.setattr(
        ServiceFactory,
        "create_metric_execution_materialization_service",
        lambda _db: FailFirstMaterialization(),
    )

    route_received_events(db_session)

    assert (
        _count(
            db_connection, "metric_plan_execution", "event_id=:id", id=first_event.id
        )
        == 0
    )
    assert (
        _count(db_connection, "event_delivery", "event_id=:id", id=first_event.id) == 0
    )
    assert (
        _count(
            db_connection, "metric_plan_execution", "event_id=:id", id=second_event.id
        )
        == 1
    )
    assert (
        _count(db_connection, "event_delivery", "event_id=:id", id=second_event.id) == 1
    )


def test_routing_failure_rolls_back_metric_materialization_for_that_event(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
    monkeypatch,
) -> None:
    _, _, _, _, _, event = _seed_runtime(
        factory,
        compiled_plans=[_compiled("routing_window_total")],
    )

    def fail_after_materialization(**_kwargs):
        raise RuntimeError("simulated crash before routing persistence")

    monkeypatch.setattr(
        "app.worker._route_materialized_event",
        fail_after_materialization,
    )

    route_received_events(db_session)

    assert (
        _count(
            db_connection, "metric_processing_execution", "event_id=:id", id=event.id
        )
        == 0
    )
    assert _count(db_connection, "event_delivery", "event_id=:id", id=event.id) == 0
    assert (
        db_connection.execute(
            text("SELECT status FROM outbox.event WHERE id=:event_id"),
            {"event_id": event.id},
        ).scalar_one()
        == "RECEIVED"
    )


def test_active_chain_without_plan_is_a_durable_configuration_failure(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
) -> None:
    project = factory.project(ProjectRecord(name="broken-metrics"))
    event_type = factory.event_type(
        EventTypeRecord(project=project, code="broken.event", name="Broken")
    )
    schema = factory.schema_definition(SchemaDefinitionRecord(event_type=event_type))
    chain = factory.processing_chain(
        ProcessingChainRecord(
            event_type=event_type,
            schema_definition=schema,
            status="ACTIVE",
            is_active=True,
        )
    )
    factory.route_definition(
        RouteDefinitionRecord(event_type=event_type, routing_key="all")
    )
    event = factory.event(EventRecord(event_type=event_type, schema_definition=schema))

    route_received_events(db_session)

    row = (
        db_connection.execute(
            text(
                "SELECT processing_chain_id, status, last_error "
                "FROM outbox.metric_processing_execution WHERE event_id=:id"
            ),
            {"id": event.id},
        )
        .mappings()
        .one()
    )
    assert row["processing_chain_id"] == chain.id
    assert row["status"] == "FAILED_CONFIGURATION"
    assert "no executable plans" in row["last_error"]
    assert _count(db_connection, "event_delivery", "event_id=:id", id=event.id) == 1


def test_runtime_never_calls_yaml_configuration_pipeline(
    factory: ObjectFactory,
    db_session: Session,
    monkeypatch,
) -> None:
    _seed_runtime(factory, compiled_plans=[_compiled("orders_total")])

    def forbidden(*_args, **_kwargs):
        raise AssertionError("configuration pipeline called at runtime")

    monkeypatch.setattr(
        "app.metrics_engine.metric_yaml_parser.parse_metric_yaml", forbidden
    )
    monkeypatch.setattr(
        "app.metrics_engine.metric_yaml_validator.validate_metric_yaml", forbidden
    )
    monkeypatch.setattr(
        "app.metrics_engine.metric_plan_compiler.compile_metric_yaml_to_json", forbidden
    )
    monkeypatch.setattr(
        "app.services.processing_chain_activation_service.ProcessingChainActivationService.rebuild_chain",
        forbidden,
    )
    monkeypatch.setattr(
        "app.services.metric_builder_service.MetricBuilderService.preview_metric",
        forbidden,
    )

    route_received_events(db_session)
    results = process_metric_plan_executions(db_session)

    assert results[0].status == "SUCCEEDED"


def test_partial_observations_are_rolled_back_when_plan_persistence_fails(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
    monkeypatch,
) -> None:
    compiled = _compiled("first_total")
    compiled["observations"].append(_compiled("second_total")["observations"][0])
    _, _, _, _, _, event = _seed_runtime(factory, compiled_plans=[compiled])
    route_received_events(db_session)
    original = AnalyticalObservationRepository.add_runtime_observation_if_absent
    calls = 0

    def fail_second(repository, observation):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("observation persistence interrupted")
        return original(repository, observation)

    monkeypatch.setattr(
        AnalyticalObservationRepository,
        "add_runtime_observation_if_absent",
        fail_second,
    )

    results = process_metric_plan_executions(db_session)

    assert results[0].status == "RETRYABLE"
    assert (
        _count(db_connection, "analytical_observation", "event_id=:id", id=event.id)
        == 0
    )


def test_retry_succeeds_without_duplicate_after_transient_failure(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
    monkeypatch,
) -> None:
    _, _, _, _, _, event = _seed_runtime(
        factory, compiled_plans=[_compiled("retry_total")]
    )
    route_received_events(db_session)
    original = AnalyticalObservationRepository.add_runtime_observation_if_absent
    failed = False

    def fail_once(repository, observation):
        nonlocal failed
        if not failed:
            failed = True
            raise RuntimeError("transient database write")
        return original(repository, observation)

    monkeypatch.setattr(
        AnalyticalObservationRepository,
        "add_runtime_observation_if_absent",
        fail_once,
    )

    results = process_metric_plan_executions(db_session)
    db_session.execute(
        text(
            "UPDATE outbox.metric_plan_execution SET next_attempt_at=NULL "
            "WHERE event_id=:event_id AND status='RETRYABLE'"
        ),
        {"event_id": event.id},
    )
    retry_results = process_metric_plan_executions(db_session)

    assert [result.status for result in results + retry_results] == [
        "RETRYABLE",
        "SUCCEEDED",
    ]
    execution = (
        db_connection.execute(
            text(
                "SELECT status, attempt_count FROM outbox.metric_plan_execution "
                "WHERE event_id=:id"
            ),
            {"id": event.id},
        )
        .mappings()
        .one()
    )
    assert execution == {"status": "SUCCEEDED", "attempt_count": 2}
    assert (
        _count(db_connection, "analytical_observation", "event_id=:id", id=event.id)
        == 1
    )


def test_repeated_technical_failure_stops_at_configured_attempt_limit(
    factory: ObjectFactory,
    db_session: Session,
    db_connection: Connection,
    monkeypatch,
) -> None:
    _, _, _, _, _, event = _seed_runtime(
        factory, compiled_plans=[_compiled("limited_retry_total")]
    )
    route_received_events(db_session)

    def always_fail(_repository, _observation):
        raise RuntimeError("persistent technical failure")

    monkeypatch.setattr(
        AnalyticalObservationRepository,
        "add_runtime_observation_if_absent",
        always_fail,
    )

    statuses = []
    for _ in range(3):
        result = process_metric_plan_executions(db_session)[0]
        statuses.append(result.status)
        db_session.execute(
            text(
                "UPDATE outbox.metric_plan_execution SET next_attempt_at=NULL "
                "WHERE event_id=:event_id AND status='RETRYABLE'"
            ),
            {"event_id": event.id},
        )

    assert statuses == ["RETRYABLE", "RETRYABLE", "FAILED_PERMANENT"]
    row = (
        db_connection.execute(
            text(
                "SELECT attempt_count, is_retryable FROM outbox.metric_plan_execution "
                "WHERE event_id=:id"
            ),
            {"id": event.id},
        )
        .mappings()
        .one()
    )
    assert row == {"attempt_count": 3, "is_retryable": False}
