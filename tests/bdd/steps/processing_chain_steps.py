from __future__ import annotations

from typing import Any

from pytest_bdd import given, parsers, then, when
from sqlalchemy import text

from tests.domain.record import (
    MetricDefinitionRecord,
    MetricDefinitionVersionRecord,
    MetricDefinitionVersionSchemaRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.context import TestContext

YAML_DOCUMENTS = {
    "valid amount": """version: "1.0"
observations:
  - code: revenue_total
    transform: identity
    value_path: $.amount
""",
    "valid revenue": """version: "1.0"
observations:
  - code: revenue_total
    transform: identity
    value_path: $.amount
    labels:
      country: $.country
""",
    "valid counter": """version: "1.0"
observations:
  - code: products_sold_total
    transform: constant
    labels:
      country: $.country
""",
    "optional revenue": """version: "1.0"
observations:
  - code: discounted_revenue_total
    transform: identity
    value_path: $.discount
""",
    "unknown path": """version: "1.0"
observations:
  - code: missing_total
    transform: identity
    value_path: $.missing
""",
    "incompatible transform": """version: "1.0"
observations:
  - code: country_total
    transform: identity
    value_path: $.country
""",
}

SCHEMA_SHAPES = {
    "complete sales": {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "minimum": 0},
            "country": {"type": "string", "enum": ["FR", "US"]},
            "discount": {"type": "number", "minimum": 0},
        },
        "required": ["amount", "country"],
    },
    "sales without country": {
        "type": "object",
        "properties": {"amount": {"type": "number", "minimum": 0}},
        "required": ["amount"],
    },
    "optional discount": {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "minimum": 0},
            "country": {"type": "string", "enum": ["FR", "US"]},
            "discount": {"type": "number", "minimum": 0},
        },
        "required": ["amount", "country"],
    },
}


def _state(ctx: TestContext) -> dict[str, Any]:
    state = getattr(ctx, "processing_chain_state", None)
    if state is None:
        state = {
            "schemas": {},
            "versions": {},
            "definitions": {},
            "candidate_id": None,
        }
        ctx.processing_chain_state = state
    return state


def _event_type(ctx: TestContext, project_name: str, event_type_code: str):
    project = ctx.probe.project.get_by_name(project_name)
    return ctx.probe.event_type.get_by_project_and_code(project, event_type_code)


@given(
    parsers.parse(
        'metric schema "{schema_name}" with shape "{shape}" exists for event '
        'type "{event_type_code}" in project "{project_name}"'
    )
)
def metric_schema_exists(
    ctx: TestContext,
    schema_name: str,
    shape: str,
    event_type_code: str,
    project_name: str,
) -> None:
    event_type = _event_type(ctx, project_name, event_type_code)
    schema = ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=event_type,
            json_schema=SCHEMA_SHAPES[shape],
            json_version_internal=schema_name,
            json_version_client=schema_name,
        )
    )
    _state(ctx)["schemas"][schema_name] = schema


@given(
    parsers.parse(
        'metric YAML version "{version_name}" using "{yaml_name}" exists for '
        'definition "{definition_name}" on event type "{event_type_code}" '
        'in project "{project_name}"'
    )
)
def metric_yaml_version_exists(
    ctx: TestContext,
    version_name: str,
    yaml_name: str,
    definition_name: str,
    event_type_code: str,
    project_name: str,
) -> None:
    state = _state(ctx)
    definition_key = f"{project_name}:{event_type_code}:{definition_name}"
    definition = state["definitions"].get(definition_key)
    if definition is None:
        definition = ctx.factory.metric_definition(
            MetricDefinitionRecord(
                event_type=_event_type(ctx, project_name, event_type_code),
                code=definition_name,
                name=definition_name,
            )
        )
        state["definitions"][definition_key] = definition
    version_number = 1 + sum(
        version.metric_definition.id == definition.id
        for version in state["versions"].values()
    )
    state["versions"][version_name] = ctx.factory.metric_definition_version(
        MetricDefinitionVersionRecord(
            metric_definition=definition,
            yaml_version_number=version_number,
            yaml_version_label=version_name,
            yaml_content=YAML_DOCUMENTS[yaml_name],
        )
    )


@given(
    parsers.parse(
        'version "{version_name}" is already compatible with schema "{schema_name}"'
    )
)
def version_is_already_compatible(
    ctx: TestContext,
    version_name: str,
    schema_name: str,
) -> None:
    state = _state(ctx)
    ctx.factory.metric_definition_version_schema(
        MetricDefinitionVersionSchemaRecord(
            metric_definition_version=state["versions"][version_name],
            schema_definition=state["schemas"][schema_name],
        )
    )


def _declare_compatibility(
    ctx: TestContext,
    version_id: int,
    schema_id: int,
) -> None:
    event_type = _event_type(ctx, "Hermes", "product.sold")
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/versions/"
        f"{version_id}/schemas/{schema_id}",
        headers=ctx.request_headers or {},
    )


@when(
    parsers.parse(
        'version "{version_name}" is declared compatible with schema "{schema_name}"'
    )
)
@when(
    parsers.parse(
        'version "{version_name}" is declared compatible with schema '
        '"{schema_name}" again'
    )
)
def version_is_declared_compatible(
    ctx: TestContext,
    version_name: str,
    schema_name: str,
) -> None:
    state = _state(ctx)
    _declare_compatibility(
        ctx,
        state["versions"][version_name].id,
        state["schemas"][schema_name].id,
    )


@when(
    parsers.parse(
        "unknown YAML version {version_id:d} is declared compatible with "
        'schema "{schema_name}"'
    )
)
def unknown_version_is_declared_compatible(
    ctx: TestContext,
    version_id: int,
    schema_name: str,
) -> None:
    _declare_compatibility(ctx, version_id, _state(ctx)["schemas"][schema_name].id)


@when(
    parsers.parse(
        'version "{version_name}" is declared compatible with unknown schema '
        "{schema_id:d}"
    )
)
def version_is_declared_against_unknown_schema(
    ctx: TestContext,
    version_name: str,
    schema_id: int,
) -> None:
    _declare_compatibility(ctx, _state(ctx)["versions"][version_name].id, schema_id)


@then(
    parsers.parse(
        'compatibility "{version_name}" to schema "{schema_name}" should '
        "exist exactly once"
    )
)
def compatibility_exists_once(
    ctx: TestContext,
    version_name: str,
    schema_name: str,
) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.metric_definition_version_schema.count_by_version_and_schema(
            state["versions"][version_name],
            state["schemas"][schema_name],
        )
        == 1
    )


@then(
    parsers.parse(
        'compatibility "{version_name}" to schema "{schema_name}" should not exist'
    )
)
def compatibility_does_not_exist(
    ctx: TestContext,
    version_name: str,
    schema_name: str,
) -> None:
    state = _state(ctx)
    assert not ctx.probe.metric_definition_version_schema.exists_by_version_and_schema(
        state["versions"][version_name], state["schemas"][schema_name]
    )


@then("no metric compatibility should have been persisted")
def no_metric_compatibility(ctx: TestContext) -> None:
    assert ctx.probe.metric_definition_version_schema.count() == 0


def _rebuild(ctx: TestContext, schema_name: str) -> None:
    state = _state(ctx)
    event_type = _event_type(ctx, "Hermes", "product.sold")
    schema = state["schemas"][schema_name]
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/schemas/"
        f"{schema.id}/processing-chain/rebuild",
        headers=ctx.request_headers or {},
    )
    if ctx.last_response.status_code == 200:
        state["candidate_id"] = ctx.last_response.json()["id"]
        state["rebuilt_candidate_id"] = state["candidate_id"]


@when(
    parsers.parse(
        'the processing chain is explicitly rebuilt for schema "{schema_name}"'
    )
)
@when(
    parsers.parse(
        'the processing chain is explicitly rebuilt for schema "{schema_name}" again'
    )
)
def processing_chain_is_rebuilt(ctx: TestContext, schema_name: str) -> None:
    _rebuild(ctx, schema_name)


@given(
    parsers.parse('the processing chain has been rebuilt for schema "{schema_name}"')
)
def processing_chain_has_been_rebuilt(ctx: TestContext, schema_name: str) -> None:
    _rebuild(ctx, schema_name)
    assert ctx.last_response.status_code == 200


def _activate_candidate(
    ctx: TestContext,
    schema_name: str,
    candidate_id: int,
) -> None:
    state = _state(ctx)
    event_type = _event_type(ctx, "Hermes", "product.sold")
    schema = state["schemas"][schema_name]
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/schemas/"
        f"{schema.id}/processing-chains/{candidate_id}/activate",
        headers=ctx.request_headers or {},
    )


@given(parsers.parse('the processing chain is active for schema "{schema_name}"'))
@when(
    parsers.parse(
        'the processing chain is built and activated for schema "{schema_name}"'
    )
)
def processing_chain_is_built_and_activated(
    ctx: TestContext,
    schema_name: str,
) -> None:
    _rebuild(ctx, schema_name)
    assert ctx.last_response.status_code == 200
    _activate_candidate(ctx, schema_name, _state(ctx)["candidate_id"])
    assert ctx.last_response.status_code == 200


@when(
    parsers.parse(
        'the rebuilt candidate is explicitly activated for schema "{schema_name}"'
    )
)
def rebuilt_candidate_is_activated(
    ctx: TestContext,
    schema_name: str,
) -> None:
    _activate_candidate(
        ctx,
        schema_name,
        _state(ctx)["rebuilt_candidate_id"],
    )
    assert ctx.last_response.status_code == 200


@then(parsers.parse('no processing snapshot should exist for schema "{schema_name}"'))
def no_processing_snapshot(ctx: TestContext, schema_name: str) -> None:
    state = _state(ctx)
    schema = state["schemas"][schema_name]
    event_type = schema.event_type
    assert ctx.probe.processing_chain.count_by_scope(event_type, schema) == 0


@then(
    parsers.parse(
        "active processing chain version {version_number:d} should exist for "
        'schema "{schema_name}"'
    )
)
def active_chain_version_exists(
    ctx: TestContext,
    version_number: int,
    schema_name: str,
) -> None:
    state = _state(ctx)
    row = ctx.probe.processing_chain.get_active_by_scope(
        _event_type(ctx, "Hermes", "product.sold"),
        state["schemas"][schema_name],
    )
    assert row["version_number"] == version_number
    state["last_active_chain_id"] = row["id"]


@then(
    parsers.parse(
        "draft processing chain version {version_number:d} should exist for "
        'schema "{schema_name}"'
    )
)
def draft_chain_version_exists(
    ctx: TestContext,
    version_number: int,
    schema_name: str,
) -> None:
    state = _state(ctx)
    row = ctx.probe.processing_chain.get_by_id(state["rebuilt_candidate_id"])
    assert row["version_number"] == version_number
    assert row["status"] == "DRAFT"
    assert row["is_active"] is False
    state["last_candidate_chain_id"] = row["id"]


@then(parsers.parse('its compiled plans should reference versions "{version_names}"'))
def compiled_plans_reference_versions(
    ctx: TestContext,
    version_names: str,
) -> None:
    state = _state(ctx)
    chain_id = state.get("last_candidate_chain_id") or state.get("last_active_chain_id")
    plans = ctx.probe.processing_plan.list_by_chain_id(chain_id)
    expected = {state["versions"][name].id for name in version_names.split(",")}
    assert {plan["metric_definition_version_id"] for plan in plans} == expected


@then("every plan in the active chain should contain a compiled document")
@then("every plan in the candidate chain should contain a compiled document")
def every_plan_is_compiled(ctx: TestContext) -> None:
    state = _state(ctx)
    chain_id = state.get("candidate_id") or state.get("last_active_chain_id")
    plans = ctx.probe.processing_plan.list_by_chain_id(chain_id)
    assert plans
    assert all(
        plan["compiled_plan_json"].get("compiler_version") == "1.1" for plan in plans
    )


@then("no AnalyticalObservation should have been produced by configuration")
def no_observation_was_produced(ctx: TestContext) -> None:
    assert ctx.probe.analytical_observation.count() == 0


@when(
    parsers.parse('the active chain identity for schema "{schema_name}" is remembered')
)
def remember_active_chain(ctx: TestContext, schema_name: str) -> None:
    state = _state(ctx)
    row = ctx.probe.processing_chain.get_active_by_scope(
        _event_type(ctx, "Hermes", "product.sold"),
        state["schemas"][schema_name],
    )
    state[f"remembered:{schema_name}"] = row["id"]


@when("the rebuilt candidate identity is remembered")
def remember_rebuilt_candidate(ctx: TestContext) -> None:
    state = _state(ctx)
    state["remembered_candidate_id"] = state["rebuilt_candidate_id"]


@then("the rebuilt candidate identity should be unchanged")
def rebuilt_candidate_is_unchanged(ctx: TestContext) -> None:
    state = _state(ctx)
    assert state["rebuilt_candidate_id"] == state["remembered_candidate_id"]


@then(
    parsers.parse(
        "the rebuilt candidate identity should equal the active chain identity "
        'for schema "{schema_name}"'
    )
)
def rebuilt_candidate_equals_active(
    ctx: TestContext,
    schema_name: str,
) -> None:
    state = _state(ctx)
    assert state["rebuilt_candidate_id"] == state[f"remembered:{schema_name}"]


@then(
    parsers.parse(
        'the active chain identity for schema "{schema_name}" should be unchanged'
    )
)
def active_chain_is_unchanged(ctx: TestContext, schema_name: str) -> None:
    state = _state(ctx)
    schema = state["schemas"][schema_name]
    row = ctx.probe.processing_chain.get_active_by_scope(
        schema.event_type,
        schema,
    )
    assert row["id"] == state[f"remembered:{schema_name}"]


@then(
    parsers.parse(
        'exactly {count:d} processing chain should exist for schema "{schema_name}"'
    )
)
@then(
    parsers.parse(
        'exactly {count:d} processing chains should exist for schema "{schema_name}"'
    )
)
def processing_chain_count(ctx: TestContext, count: int, schema_name: str) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.processing_chain.count_by_scope(
            _event_type(ctx, "Hermes", "product.sold"),
            state["schemas"][schema_name],
        )
        == count
    )


@then(
    parsers.parse(
        'only one processing chain should be active for schema "{schema_name}"'
    )
)
def only_one_chain_is_active(ctx: TestContext, schema_name: str) -> None:
    state = _state(ctx)
    schema = state["schemas"][schema_name]
    result = ctx.probe.processing_chain.connection.execute(
        text(
            """
            SELECT COUNT(*) FROM outbox.processing_chain
            WHERE event_type_id = :event_type_id
              AND schema_definition_id = :schema_id
              AND is_active = true
            """
        ),
        {
            "event_type_id": schema.event_type.id,
            "schema_id": schema.id,
        },
    )
    assert result.scalar_one() == 1


@then(
    parsers.parse('no active processing chain should exist for schema "{schema_name}"')
)
def no_active_chain(ctx: TestContext, schema_name: str) -> None:
    state = _state(ctx)
    schema = state["schemas"][schema_name]
    assert not ctx.probe.processing_chain.exists_active_by_scope(
        schema.event_type,
        schema,
    )


def _propagate(ctx: TestContext, source_name: str, target_name: str) -> None:
    state = _state(ctx)
    event_type = _event_type(ctx, "Hermes", "product.sold")
    source = state["schemas"][source_name]
    target = state["schemas"][target_name]
    if "propagation" in state:
        state["counts_before_repeated_propagation"] = {
            "chains": ctx.probe.processing_chain.count_by_scope(
                event_type,
                target,
            ),
            "plans": ctx.probe.processing_plan.count(),
        }
    state["yaml_count_before_propagation"] = ctx.probe.metric_definition_version.count()
    if ctx.probe.processing_chain.exists_active_by_scope(event_type, source):
        state["source_chain_before_propagation"] = (
            ctx.probe.processing_chain.get_active_by_scope(event_type, source)["id"]
        )
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/schemas/"
        f"{target.id}/compatibilities/propagate",
        json={"source_schema_definition_id": source.id},
        headers=ctx.request_headers or {},
    )
    if ctx.last_response.status_code == 200:
        state["propagation"] = ctx.last_response.json()
        state["candidate_id"] = state["propagation"].get(
            "candidate_processing_chain_id"
        )


@when(
    parsers.parse(
        'compatibilities are propagated from schema "{source_name}" to '
        'schema "{target_name}"'
    )
)
@when(
    parsers.parse(
        'compatibilities are propagated from schema "{source_name}" to '
        'schema "{target_name}" again'
    )
)
def compatibilities_are_propagated(
    ctx: TestContext,
    source_name: str,
    target_name: str,
) -> None:
    _propagate(ctx, source_name, target_name)


@then(
    parsers.parse(
        "the propagation should report {compatible:d} compatible and "
        "{incompatible:d} incompatible metrics"
    )
)
def propagation_counts(
    ctx: TestContext,
    compatible: int,
    incompatible: int,
) -> None:
    payload = _state(ctx)["propagation"]
    assert payload["compatible_count"] == compatible
    assert payload["incompatible_count"] == incompatible
    assert payload["evaluated_count"] == compatible + incompatible


@then(parsers.parse('the incompatibility reason should contain "{message}"'))
def incompatibility_reason(ctx: TestContext, message: str) -> None:
    results = _state(ctx)["propagation"]["results"]
    incompatible = next(result for result in results if not result["compatible"])
    assert message in incompatible["reason"]


@then("the propagation candidate should be a complete inactive draft")
def propagation_candidate_is_draft(ctx: TestContext) -> None:
    state = _state(ctx)
    assert state["propagation"]["activation_allowed"] is True
    row = ctx.probe.processing_chain.get_by_id(state["candidate_id"])
    assert row["status"] == "DRAFT"
    assert row["is_active"] is False


@then("the propagation candidate should be incomplete and inactive")
def propagation_candidate_is_incomplete(ctx: TestContext) -> None:
    state = _state(ctx)
    assert state["propagation"]["activation_allowed"] is False
    row = ctx.probe.processing_chain.get_by_id(state["candidate_id"])
    assert row["status"] == "INCOMPLETE"
    assert row["is_active"] is False


@then("no new YAML version should have been created")
def no_new_yaml_version(ctx: TestContext) -> None:
    state = _state(ctx)
    assert (
        ctx.probe.metric_definition_version.count()
        == state["yaml_count_before_propagation"]
    )


@then("the propagation should report an optional-field runtime warning")
def propagation_reports_optional_warning(ctx: TestContext) -> None:
    warnings = _state(ctx)["propagation"]["results"][0]["warnings"]
    assert any("BDD-015C" in warning for warning in warnings)


@then("the repeated propagation should create no additional chain or plan")
def repeated_propagation_creates_nothing(ctx: TestContext) -> None:
    state = _state(ctx)
    target = state["schemas"]["v2"]
    event_type = _event_type(ctx, "Hermes", "product.sold")
    remembered = state["counts_before_repeated_propagation"]
    assert (
        ctx.probe.processing_chain.count_by_scope(event_type, target)
        == remembered["chains"]
    )
    assert ctx.probe.processing_plan.count() == remembered["plans"]


@when(
    parsers.parse('the propagation candidate is activated for schema "{schema_name}"')
)
def activate_propagation_candidate(ctx: TestContext, schema_name: str) -> None:
    _activate_candidate(
        ctx,
        schema_name,
        _state(ctx)["candidate_id"],
    )


@then('the active chain for schema "v1" should remain unchanged')
def source_active_chain_remains_unchanged(ctx: TestContext) -> None:
    state = _state(ctx)
    event_type = _event_type(ctx, "Hermes", "product.sold")
    row = ctx.probe.processing_chain.get_active_by_scope(
        event_type, state["schemas"]["v1"]
    )
    assert row["id"] == state["source_chain_before_propagation"]
