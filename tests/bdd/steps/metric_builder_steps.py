"""Public API and independent SQL steps for BDD-016A."""

from __future__ import annotations

from types import SimpleNamespace

from pytest_bdd import given, parsers, then, when
from sqlalchemy import text

from tests.domain.record import (
    EventTypeRecord,
    MetricDefinitionRecord,
    ProjectRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.context import TestContext

BUILDER_SCHEMA = {
    "type": "object",
    "required": ["amount", "active", "status"],
    "properties": {
        "amount": {"type": "number", "minimum": 0},
        "unbounded_amount": {"type": "number"},
        "active": {"type": "boolean"},
        "status": {"type": "string", "enum": ["new", "done"]},
        "title": {"type": "string"},
        "customer_id": {"type": "string", "enum": ["a", "b"]},
        "items": {"type": "array", "items": {"type": "string"}},
        "nullable_name": {"type": ["null", "string"]},
        "payload": {
            "type": "object",
            "properties": {"nested": {"type": "string"}},
            "required": ["nested"],
        },
        "complex": {"anyOf": [{"type": "string"}, {"type": "boolean"}]},
    },
}


def _state(ctx: TestContext) -> SimpleNamespace:
    state = getattr(ctx, "metric_builder", None)
    if state is None:
        state = SimpleNamespace()
        ctx.metric_builder = state
    return state


def _configuration_counts(ctx: TestContext) -> tuple[int, ...]:
    return (
        ctx.probe.metric_definition.count(),
        ctx.probe.metric_definition_version.count(),
        ctx.probe.metric_definition_version_schema.count(),
        ctx.probe.processing_chain.count(),
        ctx.probe.processing_plan.count(),
    )


def _preview(
    ctx: TestContext,
    *,
    metric_code: str,
    intent: str,
    value_path: str | None = None,
    labels: dict[str, str] | None = None,
    extra: dict | None = None,
) -> None:
    state = _state(ctx)
    body = {
        "schema_definition_id": state.schema.id,
        "metric_code": metric_code,
        "intent": intent,
        "value_path": value_path,
        "labels": labels or {},
    }
    body.update(extra or {})
    state.before_counts = _configuration_counts(ctx)
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{state.event_type.id}/metric-builder/preview",
        json=body,
        headers=ctx.request_headers or {},
    )


@given("an authorized Metrics Builder schema exists")
def authorized_builder_schema(ctx: TestContext) -> None:
    state = _state(ctx)
    owner = ctx.seed.project_owner(
        project_name="bdd-builder",
        user_email="builder@example.test",
    )
    state.project = owner.project
    state.event_type = ctx.factory.event_type(
        EventTypeRecord(
            project=owner.project,
            code="order.created",
            name="Order created",
        )
    )
    state.schema = ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=state.event_type,
            json_schema=BUILDER_SCHEMA,
            json_version_internal="1",
        )
    )
    ctx.request_headers = ctx.auth.as_user(owner.user)


@when("the Builder schema fields are inspected")
def inspect_builder_fields(ctx: TestContext) -> None:
    state = _state(ctx)
    ctx.last_response = ctx.client.get(
        f"/api/admin/event-types/{state.event_type.id}/metric-builder/schema-fields",
        params={"schema_definition_id": state.schema.id},
        headers=ctx.request_headers or {},
    )


@when("the active Builder schema fields are inspected")
def inspect_active_builder_fields(ctx: TestContext) -> None:
    state = _state(ctx)
    ctx.last_response = ctx.client.get(
        f"/api/admin/event-types/{state.event_type.id}/metric-builder/schema-fields",
        headers=ctx.request_headers or {},
    )


def _response_fields(ctx: TestContext) -> dict[str, dict]:
    assert ctx.last_response is not None
    assert ctx.last_response.status_code == 200, ctx.last_response.text
    return {item["path"]: item for item in ctx.last_response.json()["fields"]}


@then("the Builder exposes required optional and nullable independently")
def required_optional_nullable(ctx: TestContext) -> None:
    fields = _response_fields(ctx)
    assert fields["$.amount"]["required"] is True
    assert fields["$.amount"]["nullable"] is False
    assert fields["$.nullable_name"]["required"] is False
    assert fields["$.nullable_name"]["nullable"] is True


@then("the nested Builder field is optional when an ancestor is optional")
def nested_optional(ctx: TestContext) -> None:
    assert _response_fields(ctx)["$.payload.nested"]["required"] is False


@then("the complex Builder field is UNSUPPORTED")
def complex_unsupported(ctx: TestContext) -> None:
    assert _response_fields(ctx)["$.complex"]["analysis_status"] == "UNSUPPORTED"


@then("only Counter-safe intents are proposed")
def exact_intents(ctx: TestContext) -> None:
    fields = _response_fields(ctx)
    assert fields["$.amount"]["value_intents"] == ["sum_value"]
    assert fields["$.unbounded_amount"]["value_intents"] == []
    assert fields["$.items"]["value_intents"] == ["count_array_items"]
    assert fields["$.title"]["value_intents"] == ["measure_string_length"]
    assert fields["$.active"]["value_intents"] == ["count_boolean_true"]


@when("each supported Builder intent is previewed")
def preview_all_intents(ctx: TestContext) -> None:
    cases = [
        ("count_event", None, {}),
        ("count_by_label", None, {"status": "$.status"}),
        ("sum_value", "$.amount", {}),
        ("count_array_items", "$.items", {}),
        ("measure_string_length", "$.title", {}),
        ("count_boolean_true", "$.active", {}),
    ]
    _state(ctx).before_counts = _configuration_counts(ctx)
    responses = []
    for index, (intent, path, labels) in enumerate(cases):
        _preview(
            ctx,
            metric_code=f"builder_metric_{index}",
            intent=intent,
            value_path=path,
            labels=labels,
        )
        responses.append(ctx.last_response)
    _state(ctx).responses = responses


@then("all six Builder previews use the expected transforms")
def previews_use_expected_transforms(ctx: TestContext) -> None:
    expected = ["constant", "constant", "identity", "count", "length", "to_number"]
    responses = _state(ctx).responses
    assert [response.status_code for response in responses] == [200] * 6
    assert [
        response.json()["compiled_plan_json"]["observations"][0]["transform"]
        for response in responses
    ] == expected


@when("sum_value is previewed on the unbounded amount")
def unsafe_sum(ctx: TestContext) -> None:
    _preview(
        ctx,
        metric_code="unsafe_sum",
        intent="sum_value",
        value_path="$.unbounded_amount",
    )


@when("count_event is previewed with a value path")
def count_event_with_path(ctx: TestContext) -> None:
    _preview(ctx, metric_code="events", intent="count_event", value_path="$.amount")


@when("count_by_label is previewed without a label")
def count_by_label_without_label(ctx: TestContext) -> None:
    _preview(ctx, metric_code="events", intent="count_by_label")


@when("count_by_label is previewed with the boolean label")
def boolean_label(ctx: TestContext) -> None:
    _preview(
        ctx,
        metric_code="events",
        intent="count_by_label",
        labels={"active": "$.active"},
    )


@when("count_by_label is previewed with the enum label")
def enum_label(ctx: TestContext) -> None:
    _preview(
        ctx,
        metric_code="events",
        intent="count_by_label",
        labels={"status": "$.status"},
    )


@when("count_by_label is previewed with the free string label")
def free_string_label(ctx: TestContext) -> None:
    _preview(
        ctx, metric_code="events", intent="count_by_label", labels={"title": "$.title"}
    )


@when("count_by_label is previewed with the identifier label")
def identifier_label(ctx: TestContext) -> None:
    _preview(
        ctx,
        metric_code="events",
        intent="count_by_label",
        labels={"customer": "$.customer_id"},
    )


@when("a Builder preview uses an interpreted JSONPath expression")
def interpreted_jsonpath(ctx: TestContext) -> None:
    _preview(
        ctx, metric_code="events", intent="sum_value", value_path="$.items[?(@.x)]"
    )


@when("a Builder preview uses a SQL injection as metric code")
def sql_injection_code(ctx: TestContext) -> None:
    _preview(ctx, metric_code="' OR 1=1 --", intent="count_event")


@when("a Builder metric is created with apostrophes and markup in free text")
def create_inert_free_text(ctx: TestContext) -> None:
    state = _state(ctx)
    state.inert_name = "O'Brien <script>alert(1)</script>"
    state.inert_description = "It's data: <b>not executable</b>"
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{state.event_type.id}/metric-builder/create",
        json={
            "schema_definition_id": state.schema.id,
            "metric_code": "inert_text_total",
            "name": state.inert_name,
            "description": state.inert_description,
            "intent": "count_event",
        },
        headers=ctx.request_headers or {},
    )


@then("the Builder free text is stored exactly as inert data")
def inert_free_text_is_exact(ctx: TestContext) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.status_code == 200, ctx.last_response.text
    row = (
        ctx.probe.connection.execute(
            text(
                "SELECT name, description FROM outbox.metric_definition "
                "WHERE code=:code"
            ),
            {"code": "inert_text_total"},
        )
        .mappings()
        .one()
    )
    assert row["name"] == _state(ctx).inert_name
    assert row["description"] == _state(ctx).inert_description


@given("an existing metric normalizes to the requested Prometheus name")
def existing_normalized_metric(ctx: TestContext) -> None:
    state = _state(ctx)
    ctx.factory.metric_definition(
        MetricDefinitionRecord(
            event_type=state.event_type,
            code="sales_total",
            name="Sales total",
        )
    )


@when("the colliding metric code is previewed")
def colliding_code(ctx: TestContext) -> None:
    _preview(ctx, metric_code="sales-total", intent="count_event")


@when("a Builder preview contains an unknown property")
def preview_unknown_property(ctx: TestContext) -> None:
    _preview(
        ctx,
        metric_code="events",
        intent="count_event",
        extra={"unknown": True},
    )


@when("a Builder preview contains too many labels")
def preview_too_many_labels(ctx: TestContext) -> None:
    state = _state(ctx)
    state.before_counts = _configuration_counts(ctx)
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{state.event_type.id}/metric-builder/preview",
        json={
            "schema_definition_id": state.schema.id,
            "metric_code": "too_many_labels",
            "intent": "sum_value",
            "value_path": "$.amount",
            "labels": {f"label_{index}": "$.active" for index in range(6)},
        },
        headers=ctx.request_headers or {},
    )


@then(parsers.parse('the Builder preview is invalid with code "{code}"'))
def invalid_preview_code(ctx: TestContext, code: str) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.status_code == 200
    body = ctx.last_response.json()
    assert body["valid"] is False
    assert body["errors"][0].startswith(code)


@then("the Builder preview is valid")
def valid_preview(ctx: TestContext) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.status_code == 200
    assert ctx.last_response.json()["valid"] is True


@then("no metric configuration is persisted by preview")
def preview_is_read_only(ctx: TestContext) -> None:
    state = _state(ctx)
    assert _configuration_counts(ctx) == state.before_counts


@given("another Project owns a Builder schema")
def another_project_schema(ctx: TestContext) -> None:
    state = _state(ctx)
    project = ctx.factory.project(ProjectRecord(name="other-builder"))
    event_type = ctx.factory.event_type(
        EventTypeRecord(project=project, code="other.event", name="Other event")
    )
    state.other_event_type = event_type
    state.other_schema = ctx.factory.schema_definition(
        SchemaDefinitionRecord(event_type=event_type, json_schema=BUILDER_SCHEMA)
    )


@when("the other Project Builder schema is inspected")
def inspect_other_project(ctx: TestContext) -> None:
    state = _state(ctx)
    ctx.last_response = ctx.client.get(
        f"/api/admin/event-types/{state.other_event_type.id}/metric-builder/schema-fields",
        params={"schema_definition_id": state.other_schema.id},
        headers=ctx.request_headers or {},
    )


@when("an unknown explicit Builder schema is inspected")
def inspect_unknown_schema(ctx: TestContext) -> None:
    state = _state(ctx)
    ctx.last_response = ctx.client.get(
        f"/api/admin/event-types/{state.event_type.id}/metric-builder/schema-fields",
        params={"schema_definition_id": 999999999},
        headers=ctx.request_headers or {},
    )


@then(parsers.parse("the Builder API responds with status {status:d}"))
def builder_status(ctx: TestContext, status: int) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.status_code == status


@then("the Builder error contains no internal technical detail")
def error_has_no_internal_detail(ctx: TestContext) -> None:
    assert ctx.last_response is not None
    body = ctx.last_response.text.lower()
    for forbidden in (
        "traceback",
        "sqlalchemy",
        "postgresql://",
        "password",
        "select ",
    ):
        assert forbidden not in body
