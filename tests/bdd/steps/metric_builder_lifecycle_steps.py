"""Public API and SQL steps for the BDD-016C lifecycle."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from pytest_bdd import given, parsers, then, when
from sqlalchemy import text

from app.services.api_key_service import ApiKeyService
from app.services.metric_yaml_service import MetricYamlService
from app.worker import (
    aggregate_prometheus_metric_state,
    process_metric_plan_executions,
    route_received_events,
)
from tests.domain.record import (
    ApiKeyRecord,
    EventTypeRecord,
    MetricDefinitionRecord,
    MetricDefinitionVersionRecord,
    MetricDefinitionVersionSchemaRecord,
    ProcessingChainRecord,
    ProcessingPlanRecord,
    RouteDefinitionRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.context import TestContext
from tests.integration.test_builder_lifecycle_concurrency import (
    _cleanup_project,
    _counts,
    _run_two_metric_workers,
    _seed_runtime_graph,
)

SCHEMA = {
    "type": "object",
    "required": ["amount", "successful"],
    "properties": {
        "amount": {"type": "number", "minimum": 0},
        "successful": {"type": "boolean"},
        "summary": {"type": ["string", "null"]},
        "provider": {"type": "string", "enum": ["aws", "gcp", "__missing__"]},
    },
}
COLLIDING_YAML = (
    ('version: "1.0"\nobservations:\n  - code: sales-total\n    transform: constant\n'),
    ('version: "1.0"\nobservations:\n  - code: sales_total\n    transform: constant\n'),
)


def _state(ctx: TestContext) -> SimpleNamespace:
    value = getattr(ctx, "metric_builder_lifecycle", None)
    if value is None:
        value = SimpleNamespace()
        ctx.metric_builder_lifecycle = value
    return value


def _builder_body(
    state: SimpleNamespace,
    *,
    code: str,
    intent: str,
    value_path: str | None = None,
    labels: dict[str, str] | None = None,
    schema_id: int | None = None,
) -> dict:
    return {
        "schema_definition_id": schema_id or state.schema.id,
        "metric_code": code,
        "name": code.replace("_", " ").title(),
        "intent": intent,
        "value_path": value_path,
        "labels": labels or {},
    }


def _create_metric(
    ctx: TestContext,
    *,
    code: str,
    intent: str,
    value_path: str | None = None,
    labels: dict[str, str] | None = None,
    event_type_id: int | None = None,
    schema_id: int | None = None,
) -> dict:
    state = _state(ctx)
    target_event_type_id = event_type_id or state.event_type.id
    body = _builder_body(
        state,
        code=code,
        intent=intent,
        value_path=value_path,
        labels=labels,
        schema_id=schema_id,
    )
    preview_body = {key: value for key, value in body.items() if key != "name"}
    preview = ctx.client.post(
        f"/api/admin/event-types/{target_event_type_id}/metric-builder/preview",
        json=preview_body,
        headers=ctx.request_headers or {},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["valid"] is True
    created = ctx.client.post(
        f"/api/admin/event-types/{target_event_type_id}/metric-builder/create",
        json=body,
        headers=ctx.request_headers or {},
    )
    assert created.status_code == 201, created.text
    return created.json()


def _rebuild(
    ctx: TestContext,
    *,
    event_type_id: int | None = None,
    schema_id: int | None = None,
):
    state = _state(ctx)
    target_event_type_id = event_type_id or state.event_type.id
    target_schema_id = schema_id or state.schema.id
    return ctx.client.post(
        f"/api/admin/event-types/{target_event_type_id}/metric-definitions/schemas/"
        f"{target_schema_id}/processing-chain/rebuild",
        headers=ctx.request_headers or {},
    )


def _activate(
    ctx: TestContext,
    chain_id: int,
    *,
    event_type_id: int | None = None,
    schema_id: int | None = None,
):
    state = _state(ctx)
    target_event_type_id = event_type_id or state.event_type.id
    target_schema_id = schema_id or state.schema.id
    return ctx.client.post(
        f"/api/admin/event-types/{target_event_type_id}/metric-definitions/schemas/"
        f"{target_schema_id}/processing-chains/{chain_id}/activate",
        headers=ctx.request_headers or {},
    )


def _ingest(
    ctx: TestContext,
    *,
    event_type_id: int | None = None,
    payload: dict | None = None,
) -> int:
    state = _state(ctx)
    response = ctx.client.post(
        "/events",
        json={
            "project_id": state.project.id,
            "event_type_id": event_type_id or state.event_type.id,
            "event_uuid": str(uuid4()),
            "json_version_internal": "1.0",
            "payload": payload or {"amount": 1, "successful": True, "provider": "aws"},
        },
        headers={"X-API-Key": state.api_key},
    )
    assert response.status_code == 200, response.text
    return int(response.json()["id"])


def _create_and_activate(
    ctx: TestContext,
    *,
    code: str = "lifecycle_events_total",
    intent: str = "count_event",
    value_path: str | None = None,
    labels: dict[str, str] | None = None,
) -> int:
    _create_metric(
        ctx,
        code=code,
        intent=intent,
        value_path=value_path,
        labels=labels,
    )
    rebuilt = _rebuild(ctx)
    assert rebuilt.status_code == 200, rebuilt.text
    activated = _activate(ctx, rebuilt.json()["id"])
    assert activated.status_code == 200, activated.text
    return int(activated.json()["id"])


@given("a BDD-016C Builder lifecycle scope exists")
def lifecycle_scope(ctx: TestContext) -> None:
    state = _state(ctx)
    owner = ctx.seed.project_owner(
        project_name="bdd-016c",
        user_email=f"bdd-016c-{uuid4().hex}@example.test",
    )
    state.project = owner.project
    state.event_type = ctx.factory.event_type(
        EventTypeRecord(
            project=owner.project,
            code=f"builder.lifecycle.{uuid4().hex}",
            name="BDD-016C lifecycle",
        )
    )
    state.schema = ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=state.event_type,
            json_schema=SCHEMA,
            json_version_internal="1.0",
        )
    )
    ctx.factory.route_definition(
        RouteDefinitionRecord(event_type=state.event_type, routing_key="all")
    )
    state.api_key = f"obx_ingest_{state.project.id}_{uuid4().hex}"
    ctx.factory.api_key(
        ApiKeyRecord(
            project=state.project,
            name="bdd-016c",
            key_prefix=state.api_key[:32],
            key_hash=ApiKeyService.hash_key(state.api_key),
        )
    )
    ctx.request_headers = ctx.auth.as_user(owner.user)


@when("a count_event metric is previewed and created")
def create_count_event(ctx: TestContext) -> None:
    _create_metric(ctx, code="lifecycle_events_total", intent="count_event")


@given("two compatible Builder metrics exist")
def two_compatible_metrics(ctx: TestContext) -> None:
    _create_metric(ctx, code="lifecycle_events_total", intent="count_event")
    _create_metric(
        ctx,
        code="lifecycle_success_total",
        intent="count_boolean_true",
        value_path="$.successful",
    )


@when("the lifecycle scope is explicitly rebuilt")
def explicit_rebuild(ctx: TestContext) -> None:
    state = _state(ctx)
    state.last_response = _rebuild(ctx)
    assert state.last_response.status_code == 200, state.last_response.text
    state.candidate = state.last_response.json()


@then(parsers.re(r"the candidate is a DRAFT containing (?P<count>\d+) exact plans?"))
def candidate_plan_count(ctx: TestContext, count: str) -> None:
    state = _state(ctx)
    assert state.candidate["status"] == "DRAFT"
    plans = ctx.probe.processing_plan.list_by_chain_id(state.candidate["id"])
    assert len(plans) == int(count)
    assert all(plan["compiled_plan_json"] is not None for plan in plans)


@given("one Builder chain is ACTIVE")
def one_active_chain(ctx: TestContext) -> None:
    state = _state(ctx)
    state.previous_active_id = _create_and_activate(ctx)


@given("another compatible Builder metric is created")
def another_metric(ctx: TestContext) -> None:
    _create_metric(
        ctx,
        code="lifecycle_success_total",
        intent="count_boolean_true",
        value_path="$.successful",
    )


@then("the previous ACTIVE chain remains unchanged")
def active_preserved(ctx: TestContext) -> None:
    state = _state(ctx)
    active = ctx.probe.processing_chain.get_active_by_scope(
        state.event_type, state.schema
    )
    assert active["id"] == state.previous_active_id


def _seed_collisions(ctx: TestContext) -> tuple[list, list]:
    state = _state(ctx)
    definitions = []
    versions = []
    for index, yaml_content in enumerate(COLLIDING_YAML):
        definition = ctx.factory.metric_definition(
            MetricDefinitionRecord(
                event_type=state.event_type,
                code="sales-total" if index == 0 else "sales_total",
                name=f"Collision {index}",
            )
        )
        version = ctx.factory.metric_definition_version(
            MetricDefinitionVersionRecord(
                metric_definition=definition,
                yaml_content=yaml_content,
            )
        )
        ctx.factory.metric_definition_version_schema(
            MetricDefinitionVersionSchemaRecord(version, state.schema)
        )
        definitions.append(definition)
        versions.append(version)
    return definitions, versions


@given("colliding historical metric versions are compatible")
def compatible_collisions(ctx: TestContext) -> None:
    _seed_collisions(ctx)


@when("the lifecycle scope rebuild is attempted")
def collision_rebuild(ctx: TestContext) -> None:
    _state(ctx).last_response = _rebuild(ctx)


@then("the lifecycle request fails with a stable collision")
def stable_collision(ctx: TestContext) -> None:
    response = _state(ctx).last_response
    assert response.status_code == 409
    assert response.json()["detail"].startswith("BUILDER_PROMETHEUS_NAME_COLLISION")


@then("no lifecycle DRAFT was persisted")
def no_draft(ctx: TestContext) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.processing_chain.count_by_scope(state.event_type, state.schema) == 0
    )


@when("the lifecycle scope is explicitly rebuilt and activated")
def rebuild_and_activate(ctx: TestContext) -> None:
    state = _state(ctx)
    rebuilt = _rebuild(ctx)
    assert rebuilt.status_code == 200, rebuilt.text
    state.last_response = _activate(ctx, rebuilt.json()["id"])
    assert state.last_response.status_code == 200, state.last_response.text


@then("exactly one lifecycle chain is ACTIVE")
def exactly_one_active(ctx: TestContext) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.processing_chain.count_where(
            "event_type_id=:event_type_id AND schema_definition_id=:schema_id "
            "AND status='ACTIVE' AND is_active=true",
            {"event_type_id": state.event_type.id, "schema_id": state.schema.id},
        )
        == 1
    )


@given("an ACTIVE chain and a colliding historical DRAFT exist")
def active_and_colliding_draft(ctx: TestContext) -> None:
    state = _state(ctx)
    definitions, versions = _seed_collisions(ctx)
    compiled = [
        MetricYamlService().compile(yaml_content, SCHEMA).compiled_plan_json
        for yaml_content in COLLIDING_YAML
    ]
    active = ctx.factory.processing_chain(
        ProcessingChainRecord(
            event_type=state.event_type,
            schema_definition=state.schema,
            status="ACTIVE",
            is_active=True,
        )
    )
    ctx.factory.processing_plan(
        ProcessingPlanRecord(
            processing_chain=active,
            metric_definition=definitions[0],
            metric_definition_version=versions[0],
            compiled_plan_json=compiled[0],
        )
    )
    candidate = ctx.factory.processing_chain(
        ProcessingChainRecord(
            event_type=state.event_type,
            schema_definition=state.schema,
            version_number=2,
        )
    )
    for position, (definition, version, plan) in enumerate(
        zip(definitions, versions, compiled, strict=True)
    ):
        ctx.factory.processing_plan(
            ProcessingPlanRecord(
                processing_chain=candidate,
                metric_definition=definition,
                metric_definition_version=version,
                position=position,
                compiled_plan_json=plan,
            )
        )
    state.previous_active_id = active.id
    state.colliding_candidate_id = candidate.id


@when("the colliding lifecycle DRAFT activation is attempted")
def activate_collision(ctx: TestContext) -> None:
    state = _state(ctx)
    state.last_response = _activate(ctx, state.colliding_candidate_id)


@when("a future lifecycle Event is ingested and processed")
def one_future_event(ctx: TestContext) -> None:
    state = _state(ctx)
    state.event_ids = [_ingest(ctx)]
    route_received_events(ctx.db_session)
    state.first_results = process_metric_plan_executions(ctx.db_session)
    aggregate_prometheus_metric_state(ctx.db_session)


@then("the future Event has one successful observation")
def one_future_observation(ctx: TestContext) -> None:
    state = _state(ctx)
    assert (
        len(ctx.probe.analytical_observation.list_by_event_id(state.event_ids[0])) == 1
    )
    assert (
        ctx.probe.metric_plan_execution.list_by_event_id(state.event_ids[0])[0][
            "status"
        ]
        == "SUCCEEDED"
    )


@given("an historical lifecycle Event was routed without a chain")
def historical_routed(ctx: TestContext) -> None:
    state = _state(ctx)
    state.historical_event_id = _ingest(ctx)
    route_received_events(ctx.db_session)
    assert (
        ctx.probe.metric_processing_execution.get_by_event_id(state.historical_event_id)
        is None
    )


@when("a Builder chain is created and activated")
def create_and_activate_chain(ctx: TestContext) -> None:
    _state(ctx).active_id = _create_and_activate(ctx)


@when("the lifecycle workers run again")
def workers_again(ctx: TestContext) -> None:
    route_received_events(ctx.db_session)
    _state(ctx).second_results = process_metric_plan_executions(ctx.db_session)


@then("the historical Event has no metric execution")
def no_historical_execution(ctx: TestContext) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.metric_processing_execution.get_by_event_id(state.historical_event_id)
        is None
    )
    assert (
        ctx.probe.analytical_observation.list_by_event_id(state.historical_event_id)
        == []
    )


@when(parsers.parse("{count:d} future lifecycle Events are ingested and processed"))
def several_future_events(ctx: TestContext, count: int) -> None:
    state = _state(ctx)
    state.event_ids = [_ingest(ctx) for _ in range(count)]
    route_received_events(ctx.db_session)
    process_metric_plan_executions(ctx.db_session)
    aggregate_prometheus_metric_state(ctx.db_session)


@then(parsers.parse("Prometheus exposes the lifecycle Counter with value {value:d}"))
def prometheus_value(ctx: TestContext, value: int) -> None:
    state = _state(ctx)
    response = ctx.client.get(f"/metrics/projects/{state.project.id}/prometheus-state")
    assert response.status_code == 200
    assert "ob1_lifecycle_events_total{" in response.text
    assert response.text.endswith(f"}} {value}\n")


@given("an optional string length Builder chain is ACTIVE")
def optional_string_chain(ctx: TestContext) -> None:
    _create_and_activate(
        ctx,
        code="optional_summary_length_total",
        intent="measure_string_length",
        value_path="$.summary",
    )


@when("a lifecycle Event without the optional field is processed")
def absent_optional_value(ctx: TestContext) -> None:
    state = _state(ctx)
    state.event_ids = [_ingest(ctx, payload={"amount": 1, "successful": True})]
    route_received_events(ctx.db_session)
    state.first_results = process_metric_plan_executions(ctx.db_session)


@when("a lifecycle Event with an allowed null is processed")
def nullable_value(ctx: TestContext) -> None:
    state = _state(ctx)
    state.event_ids = [
        _ingest(
            ctx,
            payload={"amount": 1, "successful": True, "summary": None},
        )
    ]
    route_received_events(ctx.db_session)
    state.first_results = process_metric_plan_executions(ctx.db_session)


@then("the lifecycle plan succeeds without observation")
def plan_without_observation(ctx: TestContext) -> None:
    state = _state(ctx)
    assert state.first_results[0].status == "SUCCEEDED"
    assert state.first_results[0].observation_count == 0
    assert ctx.probe.analytical_observation.list_by_event_id(state.event_ids[0]) == []


@given("an optional label Builder chain is ACTIVE")
def optional_label_chain(ctx: TestContext) -> None:
    _create_and_activate(
        ctx,
        code="lifecycle_by_provider",
        intent="count_by_label",
        labels={"provider": "$.provider"},
    )


@when("a lifecycle Event without the optional label is processed")
def absent_label(ctx: TestContext) -> None:
    state = _state(ctx)
    state.event_ids = [_ingest(ctx, payload={"amount": 1, "successful": True})]
    route_received_events(ctx.db_session)
    process_metric_plan_executions(ctx.db_session)
    aggregate_prometheus_metric_state(ctx.db_session)


@then("the lifecycle contribution has a structural null dimension")
def structural_null(ctx: TestContext) -> None:
    state = _state(ctx)
    observations = ctx.probe.analytical_observation.list_by_event_id(state.event_ids[0])
    assert observations[0]["dimensions_json"] == {"provider": None}


@then("Prometheus omits the optional lifecycle label")
def omitted_label(ctx: TestContext) -> None:
    state = _state(ctx)
    response = ctx.client.get(f"/metrics/projects/{state.project.id}/prometheus-state")
    assert response.status_code == 200
    assert "ob1_lifecycle_by_provider{" in response.text
    assert "provider=" not in response.text


@given("two lifecycle EventTypes have structurally identical schemas")
def identical_event_types(ctx: TestContext) -> None:
    state = _state(ctx)
    second_event_type = ctx.factory.event_type(
        EventTypeRecord(
            project=state.project,
            code=f"builder.lifecycle.second.{uuid4().hex}",
            name="BDD-016C second lifecycle",
        )
    )
    second_schema = ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=second_event_type,
            json_schema=SCHEMA,
            json_version_internal="1.0",
        )
    )
    state.second_event_type = second_event_type
    state.second_schema = second_schema
    for event_type, schema in (
        (state.event_type, state.schema),
        (second_event_type, second_schema),
    ):
        _create_metric(
            ctx,
            code="isolated_events_total",
            intent="count_event",
            event_type_id=event_type.id,
            schema_id=schema.id,
        )
        rebuilt = _rebuild(
            ctx,
            event_type_id=event_type.id,
            schema_id=schema.id,
        )
        assert rebuilt.status_code == 200
        activated = _activate(
            ctx,
            rebuilt.json()["id"],
            event_type_id=event_type.id,
            schema_id=schema.id,
        )
        assert activated.status_code == 200


@when("both lifecycle scopes process one Event")
def process_both_scopes(ctx: TestContext) -> None:
    state = _state(ctx)
    state.event_ids = [
        _ingest(ctx),
        _ingest(ctx, event_type_id=state.second_event_type.id),
    ]
    route_received_events(ctx.db_session)
    process_metric_plan_executions(ctx.db_session)
    aggregate_prometheus_metric_state(ctx.db_session)


@then("each lifecycle Event uses its exact chain and Prometheus scope")
def exact_isolated_scopes(ctx: TestContext) -> None:
    state = _state(ctx)
    observations = [
        ctx.probe.analytical_observation.list_by_event_id(event_id)[0]
        for event_id in state.event_ids
    ]
    assert (
        observations[0]["processing_chain_id"] != observations[1]["processing_chain_id"]
    )
    response = ctx.client.get(f"/metrics/projects/{state.project.id}/prometheus-state")
    assert response.text.count("ob1_isolated_events_total{") == 2
    assert f'ob1_event_type="{state.event_type.code}"' in response.text
    assert f'ob1_event_type="{state.second_event_type.code}"' in response.text


@given("a committed lifecycle batch for 2 metric workers")
def committed_worker_batch(ctx: TestContext, request) -> None:
    state = _state(ctx)
    project, event_type, _, _, _ = _seed_runtime_graph(
        event_count=6,
        plan_codes=("bdd_worker_a", "bdd_worker_b"),
    )
    state.committed_project = project
    state.committed_event_type = event_type
    state.expected_execution_count = 12
    request.addfinalizer(lambda: _cleanup_project(project.id))


@given("a committed lifecycle Event with one permanent metric plan")
def committed_permanent_batch(ctx: TestContext, request) -> None:
    state = _state(ctx)
    project, event_type, _, _, _ = _seed_runtime_graph(
        event_count=1,
        plan_codes=("bdd_valid_a", "bdd_invalid", "bdd_valid_c"),
        negative_plan=1,
    )
    state.committed_project = project
    state.committed_event_type = event_type
    state.expected_execution_count = 3
    request.addfinalizer(lambda: _cleanup_project(project.id))


@when("both lifecycle metric workers run concurrently")
def concurrent_metric_workers(ctx: TestContext) -> None:
    state = _state(ctx)
    state.worker_results = _run_two_metric_workers(
        require_distinct_first_acquisitions=(state.expected_execution_count > 3)
    )


@then("every lifecycle execution and observation is unique")
def unique_worker_effects(ctx: TestContext) -> None:
    state = _state(ctx)
    ids = [item for worker in state.worker_results for item in worker]
    assert len(ids) == state.expected_execution_count
    assert len(set(ids)) == state.expected_execution_count
    counts = _counts(state.committed_project.id)
    assert counts["executions"] == state.expected_execution_count
    assert counts["observations"] == state.expected_execution_count
    assert counts["pending"] == 0


@then("the permanent lifecycle plan is not retryable and other plans succeed")
def permanent_isolated(ctx: TestContext) -> None:
    state = _state(ctx)
    rows = (
        ctx.db_session.execute(
            text(
                "SELECT mpe.status, mpe.attempt_count, mpe.is_retryable FROM "
                "outbox.metric_plan_execution mpe JOIN outbox.event e "
                "ON e.id=mpe.event_id WHERE e.project_id=:project_id "
                "ORDER BY mpe.processing_plan_id"
            ),
            {"project_id": state.committed_project.id},
        )
        .mappings()
        .all()
    )
    assert [row["status"] for row in rows] == [
        "SUCCEEDED",
        "FAILED_PERMANENT",
        "SUCCEEDED",
    ]
    assert rows[1]["attempt_count"] == 1
    assert rows[1]["is_retryable"] is False
    assert _counts(state.committed_project.id)["deliveries"] == 1


@when("a future lifecycle Event is ingested and processed twice")
def process_twice(ctx: TestContext) -> None:
    state = _state(ctx)
    state.event_ids = [_ingest(ctx)]
    route_received_events(ctx.db_session)
    process_metric_plan_executions(ctx.db_session)
    aggregate_prometheus_metric_state(ctx.db_session)
    state.before_observations = ctx.probe.analytical_observation.count_where(
        "event_id=:event_id", {"event_id": state.event_ids[0]}
    )
    state.before_deliveries = ctx.probe.event_delivery.count_where(
        "event_id=:event_id", {"event_id": state.event_ids[0]}
    )
    route_received_events(ctx.db_session)
    state.second_results = process_metric_plan_executions(ctx.db_session)
    aggregate_prometheus_metric_state(ctx.db_session)


@then("the second lifecycle cycle creates no observation or delivery")
def no_second_effect(ctx: TestContext) -> None:
    state = _state(ctx)
    assert state.second_results == ()
    assert (
        ctx.probe.analytical_observation.count_where(
            "event_id=:event_id", {"event_id": state.event_ids[0]}
        )
        == state.before_observations
    )
    assert (
        ctx.probe.event_delivery.count_where(
            "event_id=:event_id", {"event_id": state.event_ids[0]}
        )
        == state.before_deliveries
    )
