from __future__ import annotations

from typing import Any

from pytest_bdd import given, parsers, then, when

from tests.domain.record import (
    MetricDefinitionRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.context import TestContext

YAML_DOCUMENTS = {
    "valid counter": """version: "1.0"
observations:
  - code: products_sold_total
    transform: constant
    labels:
      country: $.country
""",
    "valid revenue": """version: "1.0"
observations:
  - code: revenue_total
    transform: identity
    value_path: $.amount
    labels:
      country: $.country
""",
    "optional revenue": """version: "1.0"
observations:
  - code: discounted_revenue_total
    transform: identity
    value_path: $.discount
    labels:
      country: $.country
""",
    "invalid syntax": """version: ["1.0"
observations:
  - code: broken
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
    "unknown transform": """version: "1.0"
observations:
  - code: amount_median
    transform: median
    value_path: $.amount
""",
}

SALES_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "country": {"type": "string"},
        "amount": {"type": "number"},
        "discount": {"type": "number"},
    },
    "required": ["country", "amount"],
}


def _state(ctx: TestContext) -> dict[str, Any]:
    state = getattr(ctx, "metric_yaml_state", None)
    if state is None:
        state = {
            "schemas": {},
            "metric_definitions": {},
            "submitted_yaml": {},
        }
        ctx.metric_yaml_state = state
    return state


def _event_type(ctx: TestContext, project_name: str, event_type_code: str):
    project = ctx.probe.project.get_by_name(project_name)
    return ctx.probe.event_type.get_by_project_and_code(
        project=project,
        code=event_type_code,
    )


def _metric_key(project_name: str, event_type_code: str, metric_code: str) -> str:
    return f"{project_name}:{event_type_code}:{metric_code}"


def _schema_key(project_name: str, event_type_code: str) -> str:
    return f"{project_name}:{event_type_code}"


@given(
    parsers.parse(
        'a sales JSON Schema exists for event type "{event_type_code}" '
        'in project "{project_name}"'
    )
)
def sales_schema_exists(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    event_type = _event_type(ctx, project_name, event_type_code)
    schema = ctx.factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=event_type,
            json_schema=SALES_JSON_SCHEMA,
            json_version_internal="1",
            json_version_client="1.0.0",
        )
    )
    _state(ctx)["schemas"][_schema_key(project_name, event_type_code)] = schema


@given(
    parsers.parse(
        'metric definition "{metric_code}" is ready for YAML configuration '
        'on event type "{event_type_code}" in project "{project_name}"'
    )
)
def metric_definition_is_ready(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    metric_code: str,
) -> None:
    event_type = _event_type(ctx, project_name, event_type_code)
    metric_definition = ctx.factory.metric_definition(
        MetricDefinitionRecord(
            event_type=event_type,
            code=metric_code,
            name=metric_code,
        )
    )
    _state(ctx)["metric_definitions"][
        _metric_key(project_name, event_type_code, metric_code)
    ] = metric_definition


def _create_version(
    ctx: TestContext,
    yaml_name: str,
    route_event_type_code: str,
    project_name: str,
    metric_definition,
    schema,
) -> None:
    event_type = _event_type(ctx, project_name, route_event_type_code)
    yaml_content = YAML_DOCUMENTS[yaml_name]
    _state(ctx)["submitted_yaml"][metric_definition.id] = yaml_content
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/"
        f"{metric_definition.id}/versions",
        json={
            "schema_definition_id": schema.id,
            "yaml_version_label": yaml_name,
            "yaml_content": yaml_content,
        },
        headers=ctx.request_headers or {},
    )


@when(
    parsers.parse(
        'YAML "{yaml_name}" is created as a version of metric definition '
        '"{metric_code}" for event type "{event_type_code}" in project '
        '"{project_name}"'
    )
)
def yaml_version_is_created(
    ctx: TestContext,
    yaml_name: str,
    metric_code: str,
    event_type_code: str,
    project_name: str,
) -> None:
    state = _state(ctx)
    metric_definition = state["metric_definitions"][
        _metric_key(project_name, event_type_code, metric_code)
    ]
    schema = state["schemas"][_schema_key(project_name, event_type_code)]
    _create_version(
        ctx,
        yaml_name,
        event_type_code,
        project_name,
        metric_definition,
        schema,
    )


@when(
    parsers.parse(
        'YAML "{yaml_name}" is created for unknown metric definition id '
        '{metric_definition_id:d} on event type "{event_type_code}" in '
        'project "{project_name}"'
    )
)
def yaml_version_is_created_for_unknown_definition(
    ctx: TestContext,
    yaml_name: str,
    metric_definition_id: int,
    event_type_code: str,
    project_name: str,
) -> None:
    event_type = _event_type(ctx, project_name, event_type_code)
    schema = _state(ctx)["schemas"][_schema_key(project_name, event_type_code)]
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/"
        f"{metric_definition_id}/versions",
        json={
            "schema_definition_id": schema.id,
            "yaml_content": YAML_DOCUMENTS[yaml_name],
        },
        headers=ctx.request_headers or {},
    )


@when(
    parsers.parse(
        'YAML "{yaml_name}" is created using metric definition '
        '"{metric_code}" through event type "{route_event_type_code}" '
        'in project "{project_name}"'
    )
)
def yaml_version_is_created_through_another_event_type(
    ctx: TestContext,
    yaml_name: str,
    metric_code: str,
    route_event_type_code: str,
    project_name: str,
) -> None:
    state = _state(ctx)
    source_event_type_code = "product.returned"
    metric_definition = state["metric_definitions"][
        _metric_key(project_name, source_event_type_code, metric_code)
    ]
    schema = state["schemas"][_schema_key(project_name, "product.sold")]
    _create_version(
        ctx,
        yaml_name,
        route_event_type_code,
        project_name,
        metric_definition,
        schema,
    )


def _request_yaml_operation(
    ctx: TestContext,
    operation: str,
    yaml_name: str,
    project_name: str,
    event_type_code: str,
    schema_event_type_code: str | None = None,
) -> None:
    event_type = _event_type(ctx, project_name, event_type_code)
    schema_key = _schema_key(
        project_name,
        schema_event_type_code or event_type_code,
    )
    schema = _state(ctx)["schemas"][schema_key]
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/yaml/{operation}",
        json={
            "schema_definition_id": schema.id,
            "yaml_content": YAML_DOCUMENTS[yaml_name],
        },
        headers=ctx.request_headers or {},
    )


@when(
    parsers.parse(
        'YAML "{yaml_name}" is previewed for event type "{event_type_code}" '
        'in project "{project_name}"'
    )
)
def yaml_is_previewed(
    ctx: TestContext,
    yaml_name: str,
    event_type_code: str,
    project_name: str,
) -> None:
    _request_yaml_operation(ctx, "preview", yaml_name, project_name, event_type_code)


@when(
    parsers.parse(
        'YAML "{yaml_name}" is validated for event type "{event_type_code}" '
        'in project "{project_name}"'
    )
)
def yaml_is_validated(
    ctx: TestContext,
    yaml_name: str,
    event_type_code: str,
    project_name: str,
) -> None:
    _request_yaml_operation(ctx, "validate", yaml_name, project_name, event_type_code)


@when(
    parsers.parse(
        'YAML "{yaml_name}" is previewed for event type '
        '"{event_type_code}" in project "{project_name}" using the schema of '
        '"{schema_event_type_code}" in project "{schema_project_name}"'
    )
)
def yaml_is_previewed_with_another_schema(
    ctx: TestContext,
    yaml_name: str,
    event_type_code: str,
    schema_event_type_code: str,
    project_name: str,
    schema_project_name: str,
) -> None:
    event_type = _event_type(ctx, project_name, event_type_code)
    schema = _state(ctx)["schemas"][
        _schema_key(schema_project_name, schema_event_type_code)
    ]
    ctx.last_response = ctx.client.post(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/yaml/preview",
        json={
            "schema_definition_id": schema.id,
            "yaml_content": YAML_DOCUMENTS[yaml_name],
        },
        headers=ctx.request_headers or {},
    )


@when(
    parsers.parse(
        'YAML versions are listed for metric definition "{metric_code}" '
        'on event type "{event_type_code}" in project "{project_name}"'
    )
)
def yaml_versions_are_listed(
    ctx: TestContext,
    metric_code: str,
    event_type_code: str,
    project_name: str,
) -> None:
    event_type = _event_type(ctx, project_name, event_type_code)
    metric_definition = _state(ctx)["metric_definitions"][
        _metric_key(project_name, event_type_code, metric_code)
    ]
    ctx.last_response = ctx.client.get(
        f"/api/admin/event-types/{event_type.id}/metric-definitions/"
        f"{metric_definition.id}/versions",
        headers=ctx.request_headers or {},
    )


@given("the YAML version count is remembered")
def remember_yaml_version_count(ctx: TestContext) -> None:
    _state(ctx)["remembered_version_count"] = (
        ctx.probe.metric_definition_version.count()
    )


@then("the YAML version count should be unchanged")
def yaml_version_count_is_unchanged(ctx: TestContext) -> None:
    assert (
        ctx.probe.metric_definition_version.count()
        == _state(ctx)["remembered_version_count"]
    )


@then(
    parsers.parse(
        "YAML version {version_number:d} should be persisted exactly for "
        'metric definition "{metric_code}"'
    )
)
def yaml_version_is_persisted_exactly(
    ctx: TestContext,
    version_number: int,
    metric_code: str,
) -> None:
    metric_definition = next(
        metric
        for key, metric in _state(ctx)["metric_definitions"].items()
        if key.endswith(f":{metric_code}")
    )
    row = ctx.probe.metric_definition_version.get_by_metric_definition_and_version(
        metric_definition,
        version_number,
    )
    assert row["yaml_content"] == _state(ctx)["submitted_yaml"][metric_definition.id]
    assert row["is_active"] is True


@then(
    parsers.parse(
        'no YAML version should be persisted for metric definition "{metric_code}"'
    )
)
def no_yaml_version_is_persisted(ctx: TestContext, metric_code: str) -> None:
    metric_definition = next(
        metric
        for key, metric in _state(ctx)["metric_definitions"].items()
        if key.endswith(f":{metric_code}")
    )
    assert (
        ctx.probe.metric_definition_version.count_by_metric_definition(
            metric_definition
        )
        == 0
    )


@then("no ProcessingChain or ProcessingPlan should have been created")
def no_runtime_snapshot_was_created(ctx: TestContext) -> None:
    assert ctx.probe.processing_chain.count() == 0
    assert ctx.probe.processing_plan.count() == 0


@then("the YAML preview should be valid")
def yaml_preview_is_valid(ctx: TestContext) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.json()["valid"] is True


@then("the YAML validation should be valid")
def yaml_validation_is_valid(ctx: TestContext) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.json() == {"valid": True, "errors": []}


@then(
    parsers.parse('the YAML validation should be invalid with error "{expected_error}"')
)
def yaml_validation_is_invalid(
    ctx: TestContext,
    expected_error: str,
) -> None:
    assert ctx.last_response is not None
    payload = ctx.last_response.json()
    assert payload["valid"] is False
    assert expected_error in payload["errors"][0]


@then(parsers.parse('the YAML preview should be invalid with error "{expected_error}"'))
def yaml_preview_is_invalid(
    ctx: TestContext,
    expected_error: str,
) -> None:
    assert ctx.last_response is not None
    payload = ctx.last_response.json()
    assert payload["valid"] is False
    assert payload["compiled_plan_json"] is None
    assert expected_error in payload["errors"][0]


@then("the compiled value should be marked optional")
def compiled_value_is_optional(ctx: TestContext) -> None:
    assert ctx.last_response is not None
    compiled = ctx.last_response.json()["compiled_plan_json"]
    assert compiled["observations"][0]["value"]["required"] is False


@then(
    parsers.parse(
        'the compiled preview should describe counter "{metric_code}" '
        'grouped by "{label_name}"'
    )
)
def compiled_preview_describes_counter(
    ctx: TestContext,
    metric_code: str,
    label_name: str,
) -> None:
    assert ctx.last_response is not None
    compiled = ctx.last_response.json()["compiled_plan_json"]
    assert compiled["compiler_version"] == "1.1"
    observation = compiled["observations"][0]
    assert observation["metric_code"] == metric_code
    assert observation["transform"] == "constant"
    assert observation["labels"] == [
        {
            "name": label_name,
            "kind": "path",
            "path": "$.country",
            "json_type": "string",
            "required": True,
            "nullable": False,
            "iterator_path": None,
        }
    ]


@then(parsers.parse('the version history should contain versions "{versions}"'))
def version_history_contains(ctx: TestContext, versions: str) -> None:
    assert ctx.last_response is not None
    assert [item["yaml_version_number"] for item in ctx.last_response.json()] == [
        int(value) for value in versions.split(",")
    ]


@then(
    parsers.parse(
        'YAML version {version_number:d} should still contain counter "{metric_code}"'
    )
)
def yaml_history_remains_immutable(
    ctx: TestContext,
    version_number: int,
    metric_code: str,
) -> None:
    assert ctx.last_response is not None
    version = next(
        item
        for item in ctx.last_response.json()
        if item["yaml_version_number"] == version_number
    )
    assert f"code: {metric_code}" in version["yaml_content"]
