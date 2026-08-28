"""Public end-to-end proof for the complete Counter Builder lifecycle."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

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
    RouteDefinitionRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.context import TestContext

LIFECYCLE_SCHEMA = {
    "type": "object",
    "required": ["amount", "themes", "successful"],
    "properties": {
        "amount": {"type": "number", "minimum": 0},
        "themes": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": ["string", "null"]},
        "successful": {"type": "boolean"},
        "provider": {
            "type": "string",
            "enum": ["aws", "gcp", "__missing__"],
        },
    },
}

METRICS = (
    {
        "metric_code": "events_total",
        "name": "Events",
        "intent": "count_event",
    },
    {
        "metric_code": "events_by_provider",
        "name": "Events by provider",
        "intent": "count_by_label",
        "labels": {"provider": "$.provider"},
    },
    {
        "metric_code": "amount_total",
        "name": "Amount",
        "intent": "sum_value",
        "value_path": "$.amount",
    },
    {
        "metric_code": "themes_total",
        "name": "Themes",
        "intent": "count_array_items",
        "value_path": "$.themes",
    },
    {
        "metric_code": "summary_length_total",
        "name": "Summary length",
        "intent": "measure_string_length",
        "value_path": "$.summary",
    },
    {
        "metric_code": "successful_total",
        "name": "Successful",
        "intent": "count_boolean_true",
        "value_path": "$.successful",
    },
)


def _post_builder(ctx: TestContext, event_type_id: int, path: str, body: dict):
    return ctx.client.post(
        f"/api/admin/event-types/{event_type_id}/metric-builder/{path}",
        json=body,
        headers=ctx.request_headers or {},
    )


def _ingest(
    ctx: TestContext,
    *,
    project_id: int,
    event_type_id: int,
    api_key: str,
    payload: dict,
    correlation_id: str,
):
    return ctx.client.post(
        "/events",
        json={
            "project_id": project_id,
            "event_type_id": event_type_id,
            "event_uuid": str(uuid4()),
            "correlation_id": correlation_id,
            "json_version_internal": "1.0",
            "payload": payload,
        },
        headers={"X-API-Key": api_key},
    )


def test_builder_lifecycle_reaches_exact_prometheus_counters(
    ctx: TestContext,
    db_connection: Connection,
) -> None:
    """Exercise preview, create, rebuild, activation, workers and rendering."""
    owner = ctx.seed.project_owner(
        project_name="bdd-016c-lifecycle",
        user_email="bdd-016c@example.test",
    )
    event_type = ctx.factory.event_type(
        EventTypeRecord(
            project=owner.project,
            code="builder.lifecycle",
            name="Builder lifecycle",
        )
    )
    schema = ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=event_type,
            json_schema=LIFECYCLE_SCHEMA,
            json_version_internal="1.0",
        )
    )
    ctx.factory.route_definition(
        RouteDefinitionRecord(event_type=event_type, routing_key="all")
    )
    plain_key = f"obx_ingest_{owner.project.id}_bdd_016c"
    ctx.factory.api_key(
        ApiKeyRecord(
            project=owner.project,
            name="bdd-016c",
            key_prefix=plain_key[:32],
            key_hash=ApiKeyService.hash_key(plain_key),
        )
    )
    ctx.request_headers = ctx.auth.as_user(owner.user)

    fields = ctx.client.get(
        f"/api/admin/event-types/{event_type.id}/metric-builder/schema-fields",
        params={"schema_definition_id": schema.id},
        headers=ctx.request_headers,
    )
    assert fields.status_code == 200

    for metric in METRICS:
        body = {"schema_definition_id": schema.id, **metric}
        preview_body = {
            key: value for key, value in body.items() if key not in {"name"}
        }
        preview = _post_builder(ctx, event_type.id, "preview", preview_body)
        assert preview.status_code == 200, preview.text
        assert preview.json()["valid"] is True
        created = _post_builder(ctx, event_type.id, "create", body)
        assert created.status_code == 201, created.text

    assert ctx.probe.metric_definition.count_where(
        "event_type_id = :event_type_id", {"event_type_id": event_type.id}
    ) == len(METRICS)
    assert ctx.probe.processing_chain.count_by_scope(event_type, schema) == 0

    historical = _ingest(
        ctx,
        project_id=owner.project.id,
        event_type_id=event_type.id,
        api_key=plain_key,
        payload={
            "amount": 99,
            "themes": ["historic"],
            "summary": "historic",
            "successful": True,
            "provider": "aws",
        },
        correlation_id="bdd-016c-historical",
    )
    assert historical.status_code == 200, historical.text
    historical_id = historical.json()["id"]
    route_received_events(ctx.db_session)
    assert ctx.probe.metric_processing_execution.get_by_event_id(historical_id) is None

    rebuild = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/schemas/"
        f"{schema.id}/processing-chain/rebuild",
        headers=ctx.request_headers,
    )
    assert rebuild.status_code == 200, rebuild.text
    candidate = rebuild.json()
    assert candidate["status"] == "DRAFT"
    assert candidate["is_active"] is False
    assert len(ctx.probe.processing_plan.list_by_chain_id(candidate["id"])) == 6

    activate = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/schemas/"
        f"{schema.id}/processing-chains/{candidate['id']}/activate",
        headers=ctx.request_headers,
    )
    assert activate.status_code == 200, activate.text
    assert activate.json()["status"] == "ACTIVE"
    assert ctx.probe.metric_processing_execution.get_by_event_id(historical_id) is None

    payloads = (
        {
            "amount": 10,
            "themes": ["dark", "light"],
            "summary": "abc",
            "successful": True,
            "provider": "aws",
        },
        {"amount": 0, "themes": [], "successful": False},
        {
            "amount": 5,
            "themes": ["dark"],
            "summary": "xy",
            "successful": True,
            "provider": "__missing__",
        },
        {
            "amount": 0,
            "themes": [],
            "summary": None,
            "successful": False,
            "provider": "gcp",
        },
    )
    event_ids = []
    for index, payload in enumerate(payloads):
        response = _ingest(
            ctx,
            project_id=owner.project.id,
            event_type_id=event_type.id,
            api_key=plain_key,
            payload=payload,
            correlation_id=f"bdd-016c-{index}",
        )
        assert response.status_code == 200, response.text
        event_ids.append(response.json()["id"])

    with patch.object(
        MetricYamlService,
        "compile",
        side_effect=AssertionError("runtime must not compile YAML"),
    ):
        route_received_events(ctx.db_session)
        first_cycle = process_metric_plan_executions(ctx.db_session)
        second_cycle = process_metric_plan_executions(ctx.db_session)

    assert len(first_cycle) == 24
    assert second_cycle == ()
    aggregate = aggregate_prometheus_metric_state(ctx.db_session)
    assert aggregate.aggregated_count == 22
    assert aggregate.failures == ()
    assert aggregate_prometheus_metric_state(ctx.db_session).aggregated_count == 0

    rows = (
        db_connection.execute(
            text(
                "SELECT metric_code, value, dimensions_json FROM "
                "outbox.analytical_observation WHERE event_id = ANY(:event_ids) "
                "ORDER BY metric_code, event_id"
            ),
            {"event_ids": event_ids},
        )
        .mappings()
        .all()
    )
    assert len(rows) == 22
    provider_dimensions = [
        row["dimensions_json"]
        for row in rows
        if row["metric_code"] == "events_by_provider"
    ]
    assert {"provider": None} in provider_dimensions
    assert {"provider": "__missing__"} in provider_dimensions

    document_response = ctx.client.get(
        f"/metrics/projects/{owner.project.id}/prometheus-state"
    )
    assert document_response.status_code == 200, document_response.text
    document = document_response.text
    platform_labels = (
        'ob1_event_type="builder.lifecycle",ob1_project="bdd-016c-lifecycle"'
    )
    assert f"ob1_events_total{{{platform_labels}}} 4\n" in document
    assert f"ob1_events_by_provider{{{platform_labels}}} 1\n" in document
    assert (
        f'ob1_events_by_provider{{{platform_labels},provider="__missing__"}} 1\n'
        in document
    )
    assert f'ob1_events_by_provider{{{platform_labels},provider="aws"}} 1\n' in document
    assert f'ob1_events_by_provider{{{platform_labels},provider="gcp"}} 1\n' in document
    assert 'provider=""' not in document
    assert f"ob1_amount_total{{{platform_labels}}} 15\n" in document
    assert f"ob1_themes_total{{{platform_labels}}} 3\n" in document
    assert f"ob1_summary_length_total{{{platform_labels}}} 5\n" in document
    assert f"ob1_successful_total{{{platform_labels}}} 2\n" in document

    assert (
        ctx.probe.event_delivery.count_where(
            "event_id = ANY(:event_ids)",
            {"event_ids": [historical_id, *event_ids]},
        )
        == 5
    )
    route_received_events(ctx.db_session)
    assert (
        ctx.probe.event_delivery.count_where(
            "event_id = ANY(:event_ids)",
            {"event_ids": [historical_id, *event_ids]},
        )
        == 5
    )
