from __future__ import annotations

from types import SimpleNamespace

from pytest_bdd import given, parsers, then, when
from sqlalchemy import text

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
from tests.infrastructure.context import TestContext

RUNTIME_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number"},
        "items": {"type": "array", "items": {"type": "number"}},
        "name": {"type": "string"},
        "active": {"type": "boolean"},
        "country": {"type": "string"},
        "premium": {"type": "boolean"},
        "optional_amount": {"type": "number"},
        "optional_country": {"type": "string"},
    },
    "required": ["amount", "items", "name", "active", "country", "premium"],
}


def _state(ctx: TestContext) -> SimpleNamespace:
    state = getattr(ctx, "metric_runtime", None)
    if state is None:
        state = SimpleNamespace()
        setattr(ctx, "metric_runtime", state)
    return state


def _compiled(
    code: str = "runtime_total",
    *,
    transform: str = "constant",
    path: str = "",
    required: bool = True,
    json_type: str = "constant",
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
                    "json_type": json_type,
                    "required": required,
                    "iterator_path": None,
                },
                "labels": labels or [],
            }
        ],
    }


def _seed(
    ctx: TestContext,
    *,
    plans: list[dict | None] | None,
    chain_status: str = "ACTIVE",
    chain_active: bool = True,
    payload: dict | None = None,
    chain_schema_is_event_schema: bool = True,
) -> SimpleNamespace:
    state = _state(ctx)
    project = ctx.factory.project(ProjectRecord(name="bdd-runtime"))
    event_type = ctx.factory.event_type(
        EventTypeRecord(project=project, code="runtime.event", name="Runtime event")
    )
    event_schema = ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=event_type,
            json_schema=RUNTIME_SCHEMA,
            json_version_internal="1",
        )
    )
    chain_schema = event_schema
    if not chain_schema_is_event_schema:
        chain_schema = ctx.factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema=RUNTIME_SCHEMA,
                json_version_internal="2",
                is_active=False,
            )
        )
    chain = None
    persisted_plans = []
    if plans is not None:
        chain = ctx.factory.processing_chain(
            ProcessingChainRecord(
                event_type=event_type,
                schema_definition=chain_schema,
                status=chain_status,
                is_active=chain_active,
            )
        )
        for position, compiled in enumerate(plans):
            definition = ctx.factory.metric_definition(
                MetricDefinitionRecord(
                    event_type=event_type,
                    code=f"runtime_definition_{position}",
                    name=f"Runtime definition {position}",
                )
            )
            version = ctx.factory.metric_definition_version(
                MetricDefinitionVersionRecord(metric_definition=definition)
            )
            ctx.factory.metric_definition_version_schema(
                MetricDefinitionVersionSchemaRecord(
                    metric_definition_version=version,
                    schema_definition=chain_schema,
                )
            )
            persisted_plans.append(
                ctx.factory.processing_plan(
                    ProcessingPlanRecord(
                        processing_chain=chain,
                        metric_definition=definition,
                        metric_definition_version=version,
                        position=position,
                        compiled_plan_json=compiled,
                    )
                )
            )
    ctx.factory.route_definition(
        RouteDefinitionRecord(event_type=event_type, routing_key="all")
    )
    event = ctx.factory.event(
        EventRecord(
            event_type=event_type,
            schema_definition=event_schema,
            json_version_internal=event_schema.json_version_internal,
            payload=payload
            or {
                "amount": 12,
                "items": [1, 2, 3],
                "name": "shop",
                "active": True,
                "country": "FR",
                "premium": True,
            },
        )
    )
    state.project = project
    state.event_type = event_type
    state.schema = event_schema
    state.chain = chain
    state.plans = persisted_plans
    state.event = event
    return state


@given("a runtime Event with an ACTIVE compiled metric plan")
def active_compiled_plan(ctx: TestContext) -> None:
    _seed(ctx, plans=[_compiled()])


@given("a runtime Event without a ProcessingChain")
def no_processing_chain(ctx: TestContext) -> None:
    _seed(ctx, plans=None)


@given(parsers.parse("a runtime Event with only a {status} metric chain"))
def inactive_processing_chain(ctx: TestContext, status: str) -> None:
    _seed(ctx, plans=[_compiled()], chain_status=status, chain_active=False)


@given("a runtime Event whose only ACTIVE metric chain targets another schema")
def another_schema_chain(ctx: TestContext) -> None:
    _seed(ctx, plans=[_compiled()], chain_schema_is_event_schema=False)


@given("a runtime Event with three compiled metric plans")
def three_plans(ctx: TestContext) -> None:
    _seed(
        ctx,
        plans=[
            _compiled("first_total"),
            _compiled("second_total"),
            _compiled("third_total"),
        ],
    )


@given("a runtime Event with one plan containing two compiled observations")
def two_observations(ctx: TestContext) -> None:
    compiled = _compiled("first_total")
    compiled["observations"].append(_compiled("second_total")["observations"][0])
    _seed(ctx, plans=[compiled])


@given(parsers.parse("a runtime Event with the compiled transform {transform}"))
def compiled_transform(ctx: TestContext, transform: str) -> None:
    paths = {
        "constant": ("", "constant"),
        "identity": ("$.amount", "number"),
        "count": ("$.items", "array"),
        "length": ("$.name", "string"),
        "to_number": ("$.active", "boolean"),
    }
    path, json_type = paths[transform]
    _seed(
        ctx,
        plans=[_compiled(transform=transform, path=path, json_type=json_type)],
    )


@given("a runtime Event with two compiled business labels")
def two_labels(ctx: TestContext) -> None:
    labels = [
        {
            "name": "country",
            "kind": "path",
            "path": "$.country",
            "json_type": "string",
            "required": True,
            "iterator_path": None,
        },
        {
            "name": "premium",
            "kind": "path",
            "path": "$.premium",
            "json_type": "boolean",
            "required": True,
            "iterator_path": None,
        },
    ]
    _seed(ctx, plans=[_compiled(labels=labels)])


@given("a runtime Event with an absent optional value path")
def absent_optional_value(ctx: TestContext) -> None:
    _seed(
        ctx,
        plans=[
            _compiled(
                transform="identity",
                path="$.optional_amount",
                required=False,
                json_type="number",
            )
        ],
    )


@given("a runtime Event with an absent optional label")
def absent_optional_label(ctx: TestContext) -> None:
    labels = [
        {
            "name": "country",
            "kind": "path",
            "path": "$.optional_country",
            "json_type": "string",
            "required": False,
            "iterator_path": None,
        }
    ]
    _seed(ctx, plans=[_compiled(labels=labels)])


@given("a runtime Event whose country label equals __missing__")
def literal_missing_label_value(ctx: TestContext) -> None:
    labels = [
        {
            "name": "country",
            "kind": "path",
            "path": "$.country",
            "json_type": "string",
            "required": True,
            "iterator_path": None,
        }
    ]
    _seed(
        ctx,
        plans=[_compiled(labels=labels)],
        payload={
            "amount": 12,
            "items": [],
            "name": "shop",
            "active": True,
            "country": "__missing__",
            "premium": True,
        },
    )


@given("a runtime Event with three internally distinct converging counter partitions")
def converging_counter_partitions(ctx: TestContext) -> None:
    optional_country = {
        "name": "country",
        "kind": "path",
        "path": "$.optional_country",
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
    _seed(
        ctx,
        plans=[
            _compiled("converged_total", labels=[optional_country]),
            _compiled("converged_total"),
            _compiled("converged_total", labels=[empty_country]),
        ],
        payload={
            "amount": 12,
            "items": [],
            "name": "shop",
            "active": True,
            "country": "",
            "premium": True,
        },
    )


@given("a runtime Event with a successful failing and successful metric plan")
def mixed_plans(ctx: TestContext) -> None:
    _seed(
        ctx,
        plans=[
            _compiled("first_total"),
            _compiled("broken_total", transform="unknown", path="$.amount"),
            _compiled("third_total"),
        ],
    )


@given("a valid runtime Event with a negative Counter plan between two valid plans")
def negative_counter_between_valid_plans(ctx: TestContext) -> None:
    state = _seed(
        ctx,
        plans=[
            _compiled("positive_before_total"),
            _compiled(
                "negative_total",
                transform="identity",
                path="$.amount",
                json_type="number",
            ),
            _compiled("positive_after_total"),
        ],
        payload={
            "amount": -5,
            "items": [],
            "name": "shop",
            "active": True,
            "country": "FR",
            "premium": True,
        },
    )
    state.delivery_count_before_counter_execution = 0


@given("a runtime Event with an ACTIVE chain containing no plan")
def active_without_plan(ctx: TestContext) -> None:
    _seed(ctx, plans=[], chain_status="ACTIVE", chain_active=True)


@given("a runtime Event with an unknown compiled operation")
def unknown_operation(ctx: TestContext) -> None:
    _seed(ctx, plans=[_compiled(transform="unknown", path="$.amount")])


@given("a runtime Event with an ACTIVE plan lacking compiled JSON")
def active_plan_without_compiled_json(ctx: TestContext) -> None:
    _seed(ctx, plans=[None])


@given("a runtime Event with a retryable metric plan execution")
def retryable_execution(ctx: TestContext) -> None:
    state = _seed(ctx, plans=[_compiled()])
    route_received_events(ctx.db_session)
    ctx.db_session.execute(
        text(
            "UPDATE outbox.metric_plan_execution SET status='RETRYABLE', "
            "next_attempt_at=NULL WHERE event_id=:event_id"
        ),
        {"event_id": state.event.id},
    )
    state.delivery_count_before_retry = ctx.probe.event_delivery.count()


@when("the runtime worker routes and processes its metric plans")
def route_and_process(ctx: TestContext) -> None:
    route_received_events(ctx.db_session)
    _state(ctx).results = process_metric_plan_executions(ctx.db_session)


@when("the runtime worker routes and processes its metric plans twice")
def route_and_process_twice(ctx: TestContext) -> None:
    route_and_process(ctx)
    route_received_events(ctx.db_session)
    _state(ctx).second_results = process_metric_plan_executions(ctx.db_session)


@when("its metric executions are materialized")
def materialize(ctx: TestContext) -> None:
    route_received_events(ctx.db_session)


@when("another ProcessingChain becomes ACTIVE before metric execution")
def replace_active_chain(ctx: TestContext) -> None:
    state = _state(ctx)
    ctx.db_session.execute(
        text(
            "UPDATE outbox.processing_chain "
            "SET is_active=false, status='RETIRED' WHERE id=:id"
        ),
        {"id": state.chain.id},
    )
    replacement = ctx.factory.processing_chain(
        ProcessingChainRecord(
            event_type=state.event_type,
            schema_definition=state.schema,
            version_number=2,
            status="ACTIVE",
            is_active=True,
        )
    )
    first_plan = state.plans[0]
    ctx.factory.processing_plan(
        ProcessingPlanRecord(
            processing_chain=replacement,
            metric_definition=first_plan.metric_definition,
            metric_definition_version=first_plan.metric_definition_version,
            compiled_plan_json=_compiled("replacement_total"),
        )
    )
    state.replacement_chain = replacement


@when("the pending metric executions are processed")
def process_pending(ctx: TestContext) -> None:
    _state(ctx).results = process_metric_plan_executions(ctx.db_session)


@when("the independent metric retry cycle runs")
def retry_cycle(ctx: TestContext) -> None:
    _state(ctx).results = process_metric_plan_executions(ctx.db_session)


@when("runtime observations are aggregated twice")
def aggregate_twice(ctx: TestContext) -> None:
    aggregate_prometheus_metric_state(ctx.db_session)
    aggregate_prometheus_metric_state(ctx.db_session)


@then("one durable metric observation is produced from the selected plan")
def one_observation(ctx: TestContext) -> None:
    state = _state(ctx)
    rows = ctx.probe.analytical_observation.list_by_event_id(state.event.id)
    assert len(rows) == 1
    assert rows[0]["processing_chain_id"] == state.chain.id
    assert rows[0]["processing_plan_id"] == state.plans[0].id


@then("no metric execution or observation is created")
def no_metric_work(ctx: TestContext) -> None:
    state = _state(ctx)
    assert ctx.probe.metric_processing_execution.get_by_event_id(state.event.id) is None
    assert ctx.probe.analytical_observation.list_by_event_id(state.event.id) == []


@then("routing still creates its delivery")
def routing_continues(ctx: TestContext) -> None:
    state = _state(ctx)
    assert ctx.probe.event_delivery.exists_where("event_id=:id", {"id": state.event.id})


@then("the observation references the originally materialized chain")
def original_chain(ctx: TestContext) -> None:
    state = _state(ctx)
    row = ctx.probe.analytical_observation.list_by_event_id(state.event.id)[0]
    assert row["processing_chain_id"] == state.chain.id
    assert row["processing_chain_id"] != state.replacement_chain.id


@then("all three metric plan executions succeed")
def three_succeeded(ctx: TestContext) -> None:
    rows = ctx.probe.metric_plan_execution.list_by_event_id(_state(ctx).event.id)
    assert [row["status"] for row in rows] == ["SUCCEEDED"] * 3


@then("three durable metric observations are produced")
def three_observations(ctx: TestContext) -> None:
    assert (
        len(ctx.probe.analytical_observation.list_by_event_id(_state(ctx).event.id))
        == 3
    )


@then("two observations have distinct deterministic occurrence keys")
def deterministic_keys(ctx: TestContext) -> None:
    rows = ctx.probe.analytical_observation.list_by_event_id(_state(ctx).event.id)
    assert [row["observation_key"] for row in rows] == [
        "observation:0:occurrence:0",
        "observation:1:occurrence:0",
    ]


@then(parsers.parse("the metric value is {value:g}"))
def metric_value(ctx: TestContext, value: float) -> None:
    rows = ctx.probe.analytical_observation.list_by_event_id(_state(ctx).event.id)
    assert rows[0]["value"] == value


@then("the observation dimensions are country FR and premium true")
def extracted_dimensions(ctx: TestContext) -> None:
    row = ctx.probe.analytical_observation.list_by_event_id(_state(ctx).event.id)[0]
    assert row["dimensions_json"] == {"country": "FR", "premium": True}


@then("the metric plan succeeds without an observation")
def succeeds_without_observation(ctx: TestContext) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.metric_plan_execution.list_by_event_id(state.event.id)[0]["status"]
        == "SUCCEEDED"
    )
    assert ctx.probe.analytical_observation.list_by_event_id(state.event.id) == []


@then("the observation stores a null country dimension")
def null_dimension(ctx: TestContext) -> None:
    row = ctx.probe.analytical_observation.list_by_event_id(_state(ctx).event.id)[0]
    assert row["dimensions_json"] == {"country": None}


@then("metric aggregation preserves the null country partition")
def null_metric_state(ctx: TestContext) -> None:
    aggregate_prometheus_metric_state(ctx.db_session)
    row = ctx.probe.connection.execute(
        text("SELECT labels_json FROM outbox.metric_state WHERE project_id=:id"),
        {"id": _state(ctx).project.id},
    ).scalar_one()
    assert row == {"country": None}


@then("Prometheus omits the null country label")
def prometheus_omits_null_country(ctx: TestContext) -> None:
    state = _state(ctx)
    response = ctx.client.get(f"/metrics/projects/{state.project.id}/prometheus-state")
    assert response.status_code == 200
    document = response.text
    assert "country=" not in document
    assert "ob1_runtime_total{" in document


@then("the observation stores the literal __missing__ country value")
def literal_missing_observation(ctx: TestContext) -> None:
    row = ctx.probe.analytical_observation.list_by_event_id(_state(ctx).event.id)[0]
    assert row["dimensions_json"] == {"country": "__missing__"}


@then("Prometheus exposes the literal __missing__ country value")
def prometheus_exposes_literal_missing(ctx: TestContext) -> None:
    state = _state(ctx)
    aggregate_prometheus_metric_state(ctx.db_session)
    metric_state = ctx.probe.connection.execute(
        text("SELECT labels_json FROM outbox.metric_state WHERE project_id=:id"),
        {"id": state.project.id},
    ).scalar_one()
    response = ctx.client.get(f"/metrics/projects/{state.project.id}/prometheus-state")
    assert response.status_code == 200
    document = response.text
    assert metric_state == {"country": "__missing__"}
    assert 'country="__missing__"' in document


@when("the runtime metric observations are aggregated")
def aggregate_runtime_observations(ctx: TestContext) -> None:
    aggregate_prometheus_metric_state(ctx.db_session)


@when("the permanent metric execution is offered to another retry cycle")
def offer_permanent_execution_to_retry(ctx: TestContext) -> None:
    state = _state(ctx)
    state.attempts_before_retry = [
        row["attempt_count"]
        for row in ctx.probe.metric_plan_execution.list_by_event_id(state.event.id)
    ]
    state.delivery_count_before_retry = ctx.probe.event_delivery.count_where(
        "event_id=:id", {"id": state.event.id}
    )
    state.permanent_retry_results = process_metric_plan_executions(ctx.db_session)


@then("three distinct MetricState partitions remain")
def three_internal_metric_states(ctx: TestContext) -> None:
    rows = (
        ctx.probe.connection.execute(
            text(
                "SELECT labels_json FROM outbox.metric_state "
                "WHERE project_id=:id ORDER BY labels_hash"
            ),
            {"id": _state(ctx).project.id},
        )
        .scalars()
        .all()
    )
    assert len(rows) == 3
    assert {} in rows
    assert {"country": None} in rows
    assert {"country": ""} in rows


@then("the Project scrape exposes one coalesced counter with value 3")
def one_coalesced_project_counter(ctx: TestContext) -> None:
    state = _state(ctx)
    response = ctx.client.get(f"/metrics/projects/{state.project.id}/prometheus-state")
    assert response.status_code == 200
    assert response.text.count("ob1_converged_total{") == 1
    assert response.text.endswith("} 3\n")


@then(parsers.parse("the metric plan fails permanently with a {message} error"))
def permanent_failure(ctx: TestContext, message: str) -> None:
    row = ctx.probe.metric_plan_execution.list_by_event_id(_state(ctx).event.id)[0]
    assert row["status"] == "FAILED_PERMANENT"
    assert message in row["last_error"]


@then("the two successful plan observations are preserved")
def two_successes(ctx: TestContext) -> None:
    rows = ctx.probe.analytical_observation.list_by_event_id(_state(ctx).event.id)
    assert [row["metric_code"] for row in rows] == ["first_total", "third_total"]


@then("the failed plan leaves no partial observation")
def no_partial(ctx: TestContext) -> None:
    rows = ctx.probe.analytical_observation.list_by_event_id(_state(ctx).event.id)
    assert all(row["metric_code"] != "broken_total" for row in rows)


@then("the negative Counter plan fails permanently with a stable error")
def negative_counter_is_permanent(ctx: TestContext) -> None:
    rows = ctx.probe.metric_plan_execution.list_by_event_id(_state(ctx).event.id)
    assert [row["status"] for row in rows] == [
        "SUCCEEDED",
        "FAILED_PERMANENT",
        "SUCCEEDED",
    ]
    assert rows[1]["last_error"].startswith("COUNTER_VALUE_NEGATIVE:")
    assert rows[1]["is_retryable"] is False


@then("the valid surrounding plans and their MetricState values are preserved")
def valid_counter_plans_are_preserved(ctx: TestContext) -> None:
    state = _state(ctx)
    observation_codes = [
        row["metric_code"]
        for row in ctx.probe.analytical_observation.list_by_event_id(state.event.id)
    ]
    metric_state_codes = list(
        ctx.probe.connection.execute(
            text(
                "SELECT metric_code FROM outbox.metric_state "
                "WHERE project_id=:project_id ORDER BY metric_code"
            ),
            {"project_id": state.project.id},
        ).scalars()
    )
    assert observation_codes == ["positive_before_total", "positive_after_total"]
    assert metric_state_codes == ["positive_after_total", "positive_before_total"]


@then("no observation or MetricState exists for the negative Counter plan")
def no_negative_counter_persistence(ctx: TestContext) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.connection.execute(
            text(
                "SELECT COUNT(*) FROM outbox.analytical_observation "
                "WHERE event_id=:event_id AND metric_code='negative_total'"
            ),
            {"event_id": state.event.id},
        ).scalar_one()
        == 0
    )
    assert (
        ctx.probe.connection.execute(
            text(
                "SELECT COUNT(*) FROM outbox.metric_state "
                "WHERE project_id=:project_id AND metric_code='negative_total'"
            ),
            {"project_id": state.project.id},
        ).scalar_one()
        == 0
    )


@then("the parent metric execution records a completed partial failure")
def parent_records_partial_failure(ctx: TestContext) -> None:
    parent = ctx.probe.metric_processing_execution.get_by_event_id(_state(ctx).event.id)
    assert parent["status"] == "COMPLETED_WITH_ERRORS"


@then("routing keeps exactly one delivery for the Event")
def routing_keeps_one_delivery(ctx: TestContext) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.event_delivery.count_where("event_id=:id", {"id": state.event.id})
        == 1
    )


@then("the permanent metric execution is not retried")
def permanent_counter_failure_is_not_retried(ctx: TestContext) -> None:
    state = _state(ctx)
    attempts_after = [
        row["attempt_count"]
        for row in ctx.probe.metric_plan_execution.list_by_event_id(state.event.id)
    ]
    assert state.permanent_retry_results == ()
    assert attempts_after == state.attempts_before_retry == [1, 1, 1]
    assert (
        ctx.probe.event_delivery.count_where("event_id=:id", {"id": state.event.id})
        == state.delivery_count_before_retry
        == 1
    )


@then("a durable metric configuration failure is recorded")
def durable_configuration_failure(ctx: TestContext) -> None:
    row = ctx.probe.metric_processing_execution.get_by_event_id(_state(ctx).event.id)
    assert row is not None
    assert row["status"] == "FAILED_CONFIGURATION"


@then("no metric observation is produced")
def no_observation(ctx: TestContext) -> None:
    assert ctx.probe.analytical_observation.list_by_event_id(_state(ctx).event.id) == []


@then("exactly one metric execution and observation remain")
def one_execution_one_observation(ctx: TestContext) -> None:
    state = _state(ctx)
    assert len(ctx.probe.metric_plan_execution.list_by_event_id(state.event.id)) == 1
    assert len(ctx.probe.analytical_observation.list_by_event_id(state.event.id)) == 1


@then("exactly one delivery remains")
def one_delivery(ctx: TestContext) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.event_delivery.count_where("event_id=:id", {"id": state.event.id})
        == 1
    )


@then("no additional delivery is created by the metric retry")
def retry_does_not_deliver(ctx: TestContext) -> None:
    state = _state(ctx)
    assert ctx.probe.event_delivery.count() == state.delivery_count_before_retry


@then(parsers.parse("the materialized metric counter value is {value:g}"))
def metric_state_value(ctx: TestContext, value: float) -> None:
    values = ctx.probe.metric_state.values_by_project_and_metric_code(
        _state(ctx).project, "runtime_total"
    )
    assert values == [value]
