from datetime import UTC, datetime, timedelta

from pytest_bdd import given, parsers, then, when
from sqlalchemy import text

from tests.domain.record import SystemMetricRecord
from tests.infrastructure.context import TestContext


def _metric_context(ctx: TestContext):
    context = getattr(ctx, "metric_context", None)
    if context is None:
        project = ctx.seed.project_registered("metrics-fixture")
        event_type = ctx.seed.event_type_registered(
            project=project,
            code="metrics.fixture",
            name="Metrics fixture",
        )
        context = (project, event_type)
        setattr(ctx, "metric_context", context)
    return context


def _value(raw: str):
    return float(raw) if "." in raw else int(raw)


@given("system metrics exist:")
def system_metrics_exist(ctx: TestContext, datatable: list[list[str]]) -> None:
    project, event_type = _metric_context(ctx)
    now = datetime.now(UTC)
    for metric_code, raw_value in datatable[1:]:
        ctx.factory.system_metric(
            SystemMetricRecord(
                metric_code=metric_code,
                value=_value(raw_value),
                project=project,
                event_type=event_type,
                period_start=now - timedelta(hours=1),
                period_end=now,
            )
        )


@given(parsers.parse('an old system metric "{metric_code}" with value {value:g}'))
def old_system_metric(ctx: TestContext, metric_code: str, value: float) -> None:
    _create_metric(ctx, metric_code, value, datetime.now(UTC) - timedelta(minutes=2))


@given(parsers.parse('a latest system metric "{metric_code}" with value {value:g}'))
def latest_system_metric(ctx: TestContext, metric_code: str, value: float) -> None:
    _create_metric(ctx, metric_code, value, datetime.now(UTC))


def _create_metric(ctx: TestContext, metric_code: str, value: float, computed_at: datetime) -> None:
    project, event_type = _metric_context(ctx)
    metric = ctx.factory.system_metric(
        SystemMetricRecord(
            metric_code=metric_code,
            value=value,
            project=project,
            event_type=event_type,
            period_start=computed_at - timedelta(hours=1),
            period_end=computed_at,
        )
    )
    ctx.db_session.execute(
        text("UPDATE outbox.system_metric SET computed_at = :computed_at WHERE id = :id"),
        {"computed_at": computed_at, "id": metric.id},
    )


@when("all system metrics are requested")
def all_system_metrics_requested(ctx: TestContext) -> None:
    ctx.last_response = ctx.client.get("/metrics")


@when("latest system metrics are requested")
def latest_system_metrics_requested(ctx: TestContext) -> None:
    ctx.last_response = ctx.client.get("/metrics/latest")


@when("legacy Prometheus metrics are requested")
def legacy_prometheus_metrics_requested(ctx: TestContext) -> None:
    ctx.last_response = ctx.client.get("/metrics/prometheus")


@then("the system metric list should be empty")
def system_metric_list_empty(ctx: TestContext) -> None:
    assert ctx.last_response.json() == []


@then(parsers.parse("the system metric list should contain {count:d} entries"))
def system_metric_list_count(ctx: TestContext, count: int) -> None:
    assert len(ctx.last_response.json()) == count


@then(parsers.parse('the system metric "{metric_code}" should have value {value:g}'))
def system_metric_value(ctx: TestContext, metric_code: str, value: float) -> None:
    metric = next(item for item in ctx.last_response.json() if item["metric_code"] == metric_code)
    assert metric["value"] == value


@then(parsers.parse('the latest system metric "{metric_code}" should have value {value:g}'))
def latest_system_metric_value(ctx: TestContext, metric_code: str, value: float) -> None:
    system_metric_value(ctx, metric_code, value)


@then(parsers.parse('the system metric list should not contain metric "{metric_code}"'))
def system_metric_absent(ctx: TestContext, metric_code: str) -> None:
    assert all(item["metric_code"] != metric_code for item in ctx.last_response.json())


@then("the Prometheus response should end with a newline")
def prometheus_ends_with_newline(ctx: TestContext) -> None:
    assert ctx.last_response.text.endswith("\n")


@then(parsers.parse('the Prometheus response should not contain metric "{metric_name}"'))
def prometheus_metric_absent(ctx: TestContext, metric_name: str) -> None:
    assert metric_name not in ctx.last_response.text


@then(parsers.parse('the Prometheus response should contain type "{metric_name}" as "{metric_type}"'))
def prometheus_type_present(ctx: TestContext, metric_name: str, metric_type: str) -> None:
    assert f"# TYPE {metric_name} {metric_type}" in ctx.last_response.text


@then(parsers.parse('the Prometheus response should contain metric "{metric_name}" with value "{value}"'))
def prometheus_metric_value(ctx: TestContext, metric_name: str, value: str) -> None:
    assert f"{metric_name} {value}" in ctx.last_response.text
