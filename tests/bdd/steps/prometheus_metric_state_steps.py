from __future__ import annotations

import json
from typing import Any

from pytest_bdd import given, parsers, then, when

from app.container.service_factory import ServiceFactory
from app.repositories.metric_state_repository import build_checkpoint_name
from tests.domain.record import (
    AnalyticalObservationRecord,
    EventRecord,
    EventTypeRecord,
    MetricDefinitionRecord,
    MetricDefinitionVersionRecord,
    MetricStateRecord,
    ProjectRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.context import TestContext


def _state(ctx: TestContext) -> dict[str, Any]:
    state = getattr(ctx, "prometheus_metric_state", None)
    if state is None:
        state = {
            "projects": {},
            "event_types": {},
            "schemas": {},
            "events": {},
            "metric_definitions": {},
            "metric_versions": {},
            "last_observations": {},
            "aggregation_error": None,
            "first_response_text": None,
        }
        setattr(ctx, "prometheus_metric_state", state)
    return state


def _project(ctx: TestContext, project_name: str):
    projects = _state(ctx)["projects"]
    if project_name not in projects:
        projects[project_name] = ctx.factory.project(
            ProjectRecord(name=project_name)
        )
    return projects[project_name]


def _event_type(ctx: TestContext, project_name: str, event_type_code: str):
    key = (project_name, event_type_code)
    event_types = _state(ctx)["event_types"]
    if key not in event_types:
        event_types[key] = ctx.factory.event_type(
            EventTypeRecord(
                project=_project(ctx, project_name),
                code=event_type_code,
                name=event_type_code,
            )
        )
    return event_types[key]


def _observation_dependencies(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    metric_code: str,
):
    state = _state(ctx)
    stream_key = (project_name, event_type_code)
    metric_key = (project_name, event_type_code, metric_code)
    event_type = _event_type(ctx, project_name, event_type_code)

    if stream_key not in state["schemas"]:
        state["schemas"][stream_key] = ctx.factory.schema_definition(
            SchemaDefinitionRecord(event_type=event_type)
        )

    if stream_key not in state["events"]:
        state["events"][stream_key] = ctx.factory.event(
            EventRecord(
                event_type=event_type,
                schema_definition=state["schemas"][stream_key],
                payload={"source": "bdd-017"},
            )
        )

    if metric_key not in state["metric_definitions"]:
        definition = ctx.factory.metric_definition(
            MetricDefinitionRecord(
                event_type=event_type,
                code=metric_code,
                name=metric_code,
            )
        )
        state["metric_definitions"][metric_key] = definition
        state["metric_versions"][metric_key] = (
            ctx.factory.metric_definition_version(
                MetricDefinitionVersionRecord(metric_definition=definition)
            )
        )

    return (
        state["events"][stream_key],
        state["metric_definitions"][metric_key],
        state["metric_versions"][metric_key],
    )


def _add_materialized_counter(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    metric_code: str,
    value: float,
    labels: dict,
) -> None:
    project = _project(ctx, project_name)
    event_type = _event_type(ctx, project_name, event_type_code)
    ctx.factory.metric_state(
        MetricStateRecord(
            project=project,
            event_type=event_type,
            metric_code=metric_code,
            value=value,
            labels_json=labels,
        )
    )


def _add_observation(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
    metric_code: str,
    value: float,
    labels: dict,
) -> None:
    event, definition, version = _observation_dependencies(
        ctx,
        project_name,
        event_type_code,
        metric_code,
    )
    observation = ctx.factory.analytical_observation(
        AnalyticalObservationRecord(
            event=event,
            metric_definition=definition,
            metric_definition_version=version,
            metric_code=metric_code,
            value=value,
            dimensions_json=labels,
        )
    )
    _state(ctx)["last_observations"][(project_name, event_type_code)] = (
        observation.id
    )


@given(parsers.parse('Prometheus project "{project_name}" exists'))
def prometheus_project_exists(ctx: TestContext, project_name: str) -> None:
    _project(ctx, project_name)


@given(parsers.parse('project "{project_name}" has materialized counters:'))
def project_has_materialized_counters(
    ctx: TestContext,
    project_name: str,
    datatable: list[list[str]],
) -> None:
    for event_type_code, metric_code, raw_value, raw_labels in datatable[1:]:
        _add_materialized_counter(
            ctx=ctx,
            project_name=project_name,
            event_type_code=event_type_code,
            metric_code=metric_code,
            value=float(raw_value),
            labels=json.loads(raw_labels),
        )


@given(parsers.parse('project "{project_name}" has pending counter observations:'))
def project_has_pending_observations(
    ctx: TestContext,
    project_name: str,
    datatable: list[list[str]],
) -> None:
    for event_type_code, metric_code, raw_value, raw_labels in datatable[1:]:
        _add_observation(
            ctx=ctx,
            project_name=project_name,
            event_type_code=event_type_code,
            metric_code=metric_code,
            value=float(raw_value),
            labels=json.loads(raw_labels),
        )


@given(
    parsers.parse(
        'project "{project_name}" has a materialized counter with special '
        "label characters"
    )
)
def project_has_escaped_label_counter(
    ctx: TestContext,
    project_name: str,
) -> None:
    _add_materialized_counter(
        ctx=ctx,
        project_name=project_name,
        event_type_code="product.sold",
        metric_code="products_sold_total",
        value=1,
        labels={"location": 'warehouse\\zone "A"\nnight'},
    )


@when(
    parsers.parse(
        'Prometheus business state is requested for project "{project_name}"'
    )
)
def prometheus_state_requested(ctx: TestContext, project_name: str) -> None:
    project = _project(ctx, project_name)
    ctx.last_response = ctx.client.get(
        f"/metrics/projects/{project.id}/prometheus-state"
    )


@when(
    parsers.parse(
        "Prometheus business state is requested for unknown project id "
        "{project_id:d}"
    )
)
def unknown_prometheus_project_requested(
    ctx: TestContext,
    project_id: int,
) -> None:
    ctx.last_response = ctx.client.get(
        f"/metrics/projects/{project_id}/prometheus-state"
    )


@when("all pending counter observations are aggregated")
def aggregate_pending_observations(ctx: TestContext) -> None:
    service = ServiceFactory.create_metric_state_aggregation_service(
        ctx.db_session
    )
    service.aggregate_all_streams()
    ctx.db_session.flush()


@when("all pending counter observations are aggregated twice")
def aggregate_pending_observations_twice(ctx: TestContext) -> None:
    aggregate_pending_observations(ctx)
    aggregate_pending_observations(ctx)


@when("aggregation is attempted atomically")
def aggregation_is_attempted_atomically(ctx: TestContext) -> None:
    service = ServiceFactory.create_metric_state_aggregation_service(
        ctx.db_session
    )
    savepoint = ctx.db_session.begin_nested()

    try:
        service.aggregate_all_streams()
    except Exception as exc:  # The scenario asserts the explicit domain error.
        savepoint.rollback()
        _state(ctx)["aggregation_error"] = exc
        ctx.db_session.expire_all()
    else:
        savepoint.commit()


@when(
    parsers.parse(
        'Prometheus business state is requested twice for project '
        '"{project_name}"'
    )
)
def prometheus_state_requested_twice(
    ctx: TestContext,
    project_name: str,
) -> None:
    prometheus_state_requested(ctx, project_name)
    _state(ctx)["first_response_text"] = ctx.last_response.text
    prometheus_state_requested(ctx, project_name)


@then("the Prometheus business response should be empty")
def prometheus_business_response_empty(ctx: TestContext) -> None:
    assert ctx.last_response is not None
    assert ctx.last_response.text == ""


@then(
    parsers.parse(
        'project "{project_name}" should have {expected_count:d} '
        "materialized counters"
    )
)
def project_materialized_counter_count(
    ctx: TestContext,
    project_name: str,
    expected_count: int,
) -> None:
    project = _project(ctx, project_name)
    assert ctx.probe.metric_state.count_by_project(project) == expected_count


@then(
    parsers.parse(
        'metric "{metric_name}" with label "{label_name}" equal to '
        '"{label_value}" should expose value {expected_value:g}'
    )
)
def metric_series_has_value(
    ctx: TestContext,
    metric_name: str,
    label_name: str,
    label_value: str,
    expected_value: float,
) -> None:
    assert ctx.last_response is not None
    matching_lines = [
        line
        for line in ctx.last_response.text.splitlines()
        if line.startswith(f"{metric_name}{{")
        and f'{label_name}="{label_value}"' in line
    ]
    assert len(matching_lines) == 1
    assert float(matching_lines[0].rsplit(" ", 1)[1]) == expected_value


@then(parsers.parse('metric "{metric_name}" should expose {count:d} series'))
def metric_series_count(
    ctx: TestContext,
    metric_name: str,
    count: int,
) -> None:
    assert ctx.last_response is not None
    assert sum(
        line.startswith(f"{metric_name}{{")
        for line in ctx.last_response.text.splitlines()
    ) == count


@then(
    parsers.parse(
        'the Prometheus response should contain platform EventType '
        '"{event_type_code}"'
    )
)
def prometheus_contains_event_type(
    ctx: TestContext,
    event_type_code: str,
) -> None:
    assert f'ob1_event_type="{event_type_code}"' in ctx.last_response.text


@then(
    parsers.parse(
        'the Prometheus response should contain platform Project '
        '"{project_name}"'
    )
)
def prometheus_contains_project(ctx: TestContext, project_name: str) -> None:
    assert f'ob1_project="{project_name}"' in ctx.last_response.text


@then(
    parsers.parse(
        'the Prometheus response should not contain platform Project '
        '"{project_name}"'
    )
)
def prometheus_does_not_contain_project(
    ctx: TestContext,
    project_name: str,
) -> None:
    assert f'ob1_project="{project_name}"' not in ctx.last_response.text


@then(
    parsers.parse(
        'the Prometheus business response should contain metric '
        '"{metric_name}"'
    )
)
def prometheus_contains_metric(ctx: TestContext, metric_name: str) -> None:
    assert any(
        line.startswith(metric_name)
        for line in ctx.last_response.text.splitlines()
    )


@then(
    parsers.parse(
        'the Prometheus business response should not contain metric '
        '"{metric_name}"'
    )
)
def prometheus_does_not_contain_metric(
    ctx: TestContext,
    metric_name: str,
) -> None:
    assert not any(
        line.startswith(metric_name)
        for line in ctx.last_response.text.splitlines()
    )


@then(
    parsers.parse(
        'persisted business labels for project "{project_name}" should not '
        "contain platform labels"
    )
)
def persisted_labels_exclude_platform_labels(
    ctx: TestContext,
    project_name: str,
) -> None:
    project = _project(ctx, project_name)
    for labels in ctx.probe.metric_state.labels_by_project(project):
        assert not any(name.startswith("ob1_") for name in labels)


@then(parsers.parse('aggregation should fail with "{message}"'))
def aggregation_failed_explicitly(ctx: TestContext, message: str) -> None:
    error = _state(ctx)["aggregation_error"]
    assert error is not None
    assert message.lower() in str(error).lower()


@then(
    parsers.parse(
        'the aggregation checkpoint for project "{project_name}" event type '
        '"{event_type_code}" should not exist'
    )
)
def aggregation_checkpoint_absent(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = _project(ctx, project_name)
    event_type = _event_type(ctx, project_name, event_type_code)
    checkpoint_name = build_checkpoint_name(project.id, event_type.id)
    assert not ctx.probe.metric_checkpoint.exists_by_name(checkpoint_name)


@then(
    parsers.parse(
        'the aggregation checkpoint for project "{project_name}" event type '
        '"{event_type_code}" should equal the last observation'
    )
)
def aggregation_checkpoint_matches_last_observation(
    ctx: TestContext,
    project_name: str,
    event_type_code: str,
) -> None:
    project = _project(ctx, project_name)
    event_type = _event_type(ctx, project_name, event_type_code)
    checkpoint_name = build_checkpoint_name(project.id, event_type.id)
    assert ctx.probe.metric_checkpoint.last_processed_by_name(
        checkpoint_name
    ) == _state(ctx)["last_observations"][(project_name, event_type_code)]


@then(
    parsers.parse(
        'type "{metric_type}" for metric "{metric_name}" should appear once'
    )
)
def metric_type_appears_once(
    ctx: TestContext,
    metric_type: str,
    metric_name: str,
) -> None:
    assert ctx.last_response.text.count(
        f"# TYPE {metric_name} {metric_type}"
    ) == 1


@then(
    "the Prometheus business response should contain escaped special label "
    "characters"
)
def special_label_characters_are_escaped(ctx: TestContext) -> None:
    assert (
        'location="warehouse\\\\zone \\"A\\"\\nnight"'
        in ctx.last_response.text
    )


@then("both Prometheus business responses should be identical")
def repeated_prometheus_responses_are_identical(ctx: TestContext) -> None:
    assert _state(ctx)["first_response_text"] == ctx.last_response.text


@then("Prometheus families and series should be sorted")
def prometheus_families_and_series_sorted(ctx: TestContext) -> None:
    lines = ctx.last_response.text.splitlines()
    assert lines[0] == "# TYPE ob1_a_total counter"
    assert 'country="BE"' in lines[1]
    assert 'country="FR"' in lines[2]
    assert lines[3] == "# TYPE ob1_z_total counter"


@then(
    parsers.parse(
        'the Prometheus business Content-Type should be "{content_type}"'
    )
)
def prometheus_content_type(ctx: TestContext, content_type: str) -> None:
    assert ctx.last_response.headers["content-type"] == content_type


@then(
    parsers.parse(
        'materialized metric "{metric_code}" in project "{project_name}" '
        "should still have value {expected_value:g}"
    )
)
def materialized_metric_value_unchanged(
    ctx: TestContext,
    metric_code: str,
    project_name: str,
    expected_value: float,
) -> None:
    project = _project(ctx, project_name)
    assert ctx.probe.metric_state.values_by_project_and_metric_code(
        project,
        metric_code,
    ) == [expected_value]
