"""Measure the real Counter runtime pipeline without defining a product SLA."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from threading import Barrier, Event
from time import perf_counter_ns
from uuid import uuid4

import httpx
from sqlalchemy import text

from app.container.service_factory import ServiceFactory
from app.database import SessionLocal, engine
from app.services.api_key_service import ApiKeyService
from app.services.config_service import ConfigService
from app.worker import (
    aggregate_prometheus_metric_state,
    process_metric_plan_executions,
    route_received_events,
)
from tests.domain.record import (
    ApiKeyRecord,
    EventTypeRecord,
    ProjectRecord,
    RouteDefinitionRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.object_factory import ObjectFactory

FORMAT_VERSION = "1.0"
DEFAULT_OUTPUT_DIRECTORY = Path("/tmp/ob1-metric-baseline")


@dataclass(frozen=True)
class BaselineProfile:
    """Parameters controlling one reproducible baseline execution."""

    events: int = 100
    payload_bytes: int = 1024
    plans: int = 5
    producers: int = 4
    metric_workers: int = 1
    metric_batch_size: int = 100


@dataclass(frozen=True)
class PipelineCounts:
    """Exact durable completion counters used by bounded polling."""

    accepted_events: int
    received_events: int
    terminal_executions: int
    observations: int
    deliveries: int
    checkpoint_observation_id: int
    last_observation_id: int


def percentile(values: list[float], quantile: float) -> float:
    """Return a deterministic linearly interpolated percentile."""
    if not values:
        raise ValueError("At least one value is required")
    if quantile < 0 or quantile > 1:
        raise ValueError("Quantile must be between zero and one")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_durations(values: list[float]) -> dict[str, float]:
    """Summarize milliseconds without imposing a pass/fail threshold."""
    if not values:
        return {"median_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}
    return {
        "median_ms": median(values),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
        "max_ms": max(values),
    }


def expected_pipeline_counts(profile: BaselineProfile) -> dict[str, int]:
    """Return functional counts that make the baseline integrity-blocking."""
    return {
        "events": profile.events,
        "executions": profile.events * profile.plans,
        "observations": profile.events * profile.plans,
        "deliveries": profile.events,
        "metric_states": profile.plans,
    }


def validate_profile(profile: BaselineProfile, *, configured_batch_size: int) -> None:
    """Reject profiles the single-worker harness cannot faithfully execute."""
    if profile.events <= 0 or profile.producers <= 0:
        raise ValueError("Events and producers must be positive")
    if profile.metric_workers != 1:
        raise ValueError("This baseline harness executes exactly one metric worker")
    if profile.metric_batch_size != configured_batch_size:
        raise ValueError(
            "The reported metric batch size must match the application configuration"
        )


def wait_for_pipeline_completion(
    load_counts: Callable[[], PipelineCounts],
    *,
    expected: dict[str, int],
    timeout_seconds: float,
    poll_interval_seconds: float,
    monotonic_ns: Callable[[], int] = perf_counter_ns,
    wait: Callable[[float], None] | None = None,
) -> tuple[PipelineCounts, int]:
    """Poll durable completion with a timeout and return the maximum backlog."""
    waiter = wait or Event().wait
    started = monotonic_ns()
    maximum_backlog = 0
    while True:
        last_counts = load_counts()
        backlog = last_counts.received_events + max(
            expected["executions"] - last_counts.terminal_executions,
            0,
        )
        maximum_backlog = max(maximum_backlog, backlog)
        complete = (
            last_counts.accepted_events == expected["events"]
            and last_counts.received_events == 0
            and last_counts.terminal_executions == expected["executions"]
            and last_counts.observations == expected["observations"]
            and last_counts.deliveries == expected["deliveries"]
            and last_counts.checkpoint_observation_id >= last_counts.last_observation_id
        )
        if complete:
            return last_counts, maximum_backlog
        elapsed = (monotonic_ns() - started) / 1_000_000_000
        if elapsed >= timeout_seconds:
            raise TimeoutError(
                f"Metric baseline timed out with durable counts {asdict(last_counts)}"
            )
        waiter(poll_interval_seconds)


def write_reports(report: dict, output_directory: Path) -> tuple[Path, Path]:
    """Write deterministic JSON and readable Markdown outside tracked sources."""
    output_directory.mkdir(parents=True, exist_ok=True)
    run_id = report["run_id"]
    json_path = output_directory / f"metric-pipeline-{run_id}.json"
    markdown_path = output_directory / f"metric-pipeline-{run_id}.md"
    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    ingress = report["statistics"]["ingress"]
    runtime = report["statistics"]["runtime_total"]
    markdown_path.write_text(
        "\n".join(
            (
                "# OB1 metric pipeline baseline",
                "",
                f"- Run: `{run_id}`",
                f"- Commit: `{report['commit_sha']}`",
                f"- Events: {report['profile']['events']}",
                f"- Plans per Event: {report['profile']['plans']}",
                f"- Throughput: {report['throughput_events_per_second']:.3f} Events/s",
                (
                    f"- Ingress median / p95 / p99: "
                    f"{ingress['median_ms']:.3f} / {ingress['p95_ms']:.3f} / "
                    f"{ingress['p99_ms']:.3f} ms"
                ),
                (
                    f"- Total median / p95 / p99: "
                    f"{runtime['median_ms']:.3f} / {runtime['p95_ms']:.3f} / "
                    f"{runtime['p99_ms']:.3f} ms"
                ),
                f"- Backlog drain: {report['drain_time_ms']:.3f} ms",
                f"- Maximum measured backlog: {report['maximum_backlog']}",
                (
                    f"- Functional integrity: "
                    f"{'PASS' if report['integrity']['passed'] else 'FAIL'}"
                ),
                "",
                (
                    "This comparative baseline is not an SLA and has no temporal "
                    "pass/fail threshold."
                ),
                "",
            )
        ),
        encoding="utf-8",
    )
    return json_path, markdown_path


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _memory_megabytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except OSError:
        return None
    return None


def _docker_version() -> str | None:
    try:
        return subprocess.run(
            ["docker", "--version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _setup_scope(run_id: str, profile: BaselineProfile) -> tuple[int, int, str]:
    schema_json = {
        "type": "object",
        "required": ["amount", "items", "summary", "successful", "padding"],
        "properties": {
            "amount": {"type": "number", "minimum": 0},
            "items": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string"},
            "successful": {"type": "boolean"},
            "padding": {"type": "string"},
        },
    }
    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"baseline-{run_id}"))
        event_type = factory.event_type(
            EventTypeRecord(
                project=project,
                code=f"baseline.{run_id}",
                name="Metric pipeline baseline",
            )
        )
        schema = factory.schema_definition(
            SchemaDefinitionRecord(
                event_type=event_type,
                json_schema=schema_json,
                json_version_internal="1.0",
            )
        )
        factory.route_definition(
            RouteDefinitionRecord(
                event_type=event_type,
                routing_key="all",
                destination_url="https://local.test/baseline",
            )
        )
        api_key = f"obx_ingest_baseline_{run_id}_{uuid4().hex}"
        factory.api_key(
            ApiKeyRecord(
                project=project,
                name="baseline",
                key_prefix=api_key[:32],
                key_hash=ApiKeyService.hash_key(api_key),
            )
        )

    metrics = (
        ("baseline_events_total", "count_event", None),
        ("baseline_amount_total", "sum_value", "$.amount"),
        ("baseline_items_total", "count_array_items", "$.items"),
        ("baseline_summary_length_total", "measure_string_length", "$.summary"),
        ("baseline_successful_total", "count_boolean_true", "$.successful"),
    )
    if profile.plans != len(metrics):
        raise ValueError(f"This baseline profile requires exactly {len(metrics)} plans")
    with SessionLocal() as session:
        builder = ServiceFactory.create_metric_builder_service(session)
        for code, intent, value_path in metrics:
            builder.create_metric_from_builder(
                event_type_id=event_type.id,
                schema_definition_id=schema.id,
                code=code,
                name=code,
                description="BDD-016C performance baseline",
                intent=intent,
                value_path=value_path,
                labels={},
            )
        lifecycle = ServiceFactory.create_processing_chain_activation_service(session)
        candidate = lifecycle.rebuild_chain(event_type.id, schema.id)
        lifecycle.activate_chain(event_type.id, schema.id, candidate.id)
    return project.id, event_type.id, api_key


def _cleanup_scope(project_id: int) -> None:
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
        "DELETE FROM outbox.api_key WHERE project_id=:project_id",
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


def _payload(profile: BaselineProfile) -> dict:
    fixed = {
        "amount": 1,
        "items": ["a", "b", "c"],
        "summary": "baseline-summary",
        "successful": True,
    }
    encoded = len(json.dumps({**fixed, "padding": ""}).encode("utf-8"))
    return {**fixed, "padding": "x" * max(profile.payload_bytes - encoded, 0)}


def _ingest_events(
    *,
    base_url: str,
    project_id: int,
    event_type_id: int,
    api_key: str,
    profile: BaselineProfile,
    run_id: str,
) -> tuple[list[int], list[float], dict[int, int]]:
    start = Barrier(profile.producers)
    event_ids: list[int] = []
    latencies_ms: list[float] = []
    accepted_ns: dict[int, int] = {}
    assignments = [
        list(range(index, profile.events, profile.producers))
        for index in range(profile.producers)
    ]

    def producer(indexes: list[int]) -> tuple[list[int], list[float], dict[int, int]]:
        local_ids: list[int] = []
        local_latencies: list[float] = []
        local_accepted: dict[int, int] = {}
        with httpx.Client(base_url=base_url, timeout=30) as client:
            start.wait(timeout=10)
            for index in indexes:
                started = perf_counter_ns()
                response = client.post(
                    "/events",
                    json={
                        "project_id": project_id,
                        "event_type_id": event_type_id,
                        "event_uuid": str(uuid4()),
                        "correlation_id": f"baseline-{run_id}-{index}",
                        "json_version_internal": "1.0",
                        "payload": _payload(profile),
                    },
                    headers={"X-API-Key": api_key},
                )
                completed = perf_counter_ns()
                response.raise_for_status()
                event_id = int(response.json()["id"])
                local_ids.append(event_id)
                local_latencies.append((completed - started) / 1_000_000)
                local_accepted[event_id] = completed
        return local_ids, local_latencies, local_accepted

    with ThreadPoolExecutor(max_workers=profile.producers) as executor:
        for future in [executor.submit(producer, indexes) for indexes in assignments]:
            ids, latencies, accepted = future.result(timeout=120)
            event_ids.extend(ids)
            latencies_ms.extend(latencies)
            accepted_ns.update(accepted)
    return event_ids, latencies_ms, accepted_ns


def _load_counts(project_id: int, event_type_id: int) -> PipelineCounts:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT "
                "(SELECT COUNT(*) FROM outbox.event WHERE project_id=:project_id), "
                "(SELECT COUNT(*) FROM outbox.event WHERE project_id=:project_id "
                "AND status='RECEIVED'), "
                "(SELECT COUNT(*) FROM outbox.metric_plan_execution mpe JOIN "
                "outbox.event e ON e.id=mpe.event_id WHERE e.project_id=:project_id "
                "AND mpe.status IN ('SUCCEEDED','FAILED_PERMANENT')), "
                "(SELECT COUNT(*) FROM outbox.analytical_observation "
                "WHERE project_id=:project_id), "
                "(SELECT COUNT(*) FROM outbox.event_delivery ed JOIN outbox.event e "
                "ON e.id=ed.event_id WHERE e.project_id=:project_id), "
                "COALESCE((SELECT last_processed_observation_id FROM "
                "outbox.metric_checkpoint WHERE checkpoint_name=:checkpoint), 0), "
                "COALESCE((SELECT MAX(id) FROM outbox.analytical_observation "
                "WHERE project_id=:project_id), 0)"
            ),
            {
                "project_id": project_id,
                "checkpoint": f"prometheus_metric_state:{project_id}:{event_type_id}",
            },
        ).one()
    return PipelineCounts(*(int(value) for value in row))


def _phase_durations(project_id: int) -> dict[str, list[float]]:
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT EXTRACT(EPOCH FROM (MIN(mpe.started_at)-e.created_at))*1000 "
                    "AS worker_wait_ms, EXTRACT(EPOCH FROM "
                    "(MAX(mpe.succeeded_at)-MIN(mpe.started_at)))*1000 AS plans_ms, "
                    "EXTRACT(EPOCH FROM (MAX(ao.observed_at)-e.created_at))*1000 "
                    "AS observation_ms, EXTRACT(EPOCH FROM "
                    "(MAX(ms.updated_at)-e.created_at))*1000 AS total_ms "
                    "FROM outbox.event e JOIN outbox.metric_plan_execution mpe "
                    "ON mpe.event_id=e.id JOIN outbox.analytical_observation ao "
                    "ON ao.event_id=e.id CROSS JOIN outbox.metric_state ms "
                    "WHERE e.project_id=:project_id AND ms.project_id=:project_id "
                    "GROUP BY e.id, e.created_at ORDER BY e.id"
                ),
                {"project_id": project_id},
            )
            .mappings()
            .all()
        )
    return {
        key: [float(row[key]) for row in rows]
        for key in ("worker_wait_ms", "plans_ms", "observation_ms", "total_ms")
    }


def run_baseline(
    *,
    base_url: str,
    output_directory: Path,
    profile: BaselineProfile,
    timeout_seconds: float,
) -> tuple[dict, Path, Path]:
    """Execute the baseline and fail only on integrity or bounded timeout."""
    configured_batch_size = ConfigService().get_metric_execution_batch_size()
    validate_profile(profile, configured_batch_size=configured_batch_size)
    run_id = uuid4().hex[:12]
    expected = expected_pipeline_counts(profile)
    project_id: int | None = None
    errors: list[str] = []
    started_ns = perf_counter_ns()
    try:
        project_id, event_type_id, api_key = _setup_scope(run_id, profile)
        event_ids, ingress_latencies, accepted_ns = _ingest_events(
            base_url=base_url,
            project_id=project_id,
            event_type_id=event_type_id,
            api_key=api_key,
            profile=profile,
            run_id=run_id,
        )
        ingress_completed_ns = perf_counter_ns()
        route_received_events()
        while process_metric_plan_executions():
            pass
        while aggregate_prometheus_metric_state().aggregated_count:
            pass
        state_ready_ns = perf_counter_ns()
        counts, polled_maximum_backlog = wait_for_pipeline_completion(
            lambda: _load_counts(project_id, event_type_id),
            expected=expected,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=0.05,
        )
        maximum_backlog = max(
            profile.events,
            expected["executions"],
            polled_maximum_backlog,
        )
        with engine.connect() as connection:
            state_rows = (
                connection.execute(
                    text(
                        "SELECT metric_code, value FROM outbox.metric_state "
                        "WHERE project_id=:project_id ORDER BY metric_code"
                    ),
                    {"project_id": project_id},
                )
                .mappings()
                .all()
            )
            postgres_version = str(
                connection.execute(text("SHOW server_version")).scalar_one()
            )
        expected_values = {
            "baseline_amount_total": float(profile.events),
            "baseline_events_total": float(profile.events),
            "baseline_items_total": float(profile.events * 3),
            "baseline_successful_total": float(profile.events),
            "baseline_summary_length_total": float(
                profile.events * len("baseline-summary")
            ),
        }
        actual_values = {row["metric_code"]: float(row["value"]) for row in state_rows}
        if len(event_ids) != len(set(event_ids)):
            errors.append("Duplicate Event identifiers returned by ingress")
        if actual_values != expected_values:
            errors.append(
                f"MetricState values differ: expected={expected_values} actual={actual_values}"
            )
        if counts != PipelineCounts(
            accepted_events=expected["events"],
            received_events=0,
            terminal_executions=expected["executions"],
            observations=expected["observations"],
            deliveries=expected["deliveries"],
            checkpoint_observation_id=counts.last_observation_id,
            last_observation_id=counts.last_observation_id,
        ):
            errors.append(f"Durable counts differ: {asdict(counts)}")
        phases = _phase_durations(project_id)
        total_client_ms = [
            (state_ready_ns - accepted_ns[event_id]) / 1_000_000
            for event_id in event_ids
        ]
        elapsed_seconds = (state_ready_ns - started_ns) / 1_000_000_000
        report = {
            "format_version": FORMAT_VERSION,
            "run_id": run_id,
            "commit_sha": _git_sha(),
            "date_utc": datetime.now(UTC).isoformat(),
            "profile": asdict(profile),
            "environment": {
                "os": platform.platform(),
                "python": sys.version.split()[0],
                "postgresql": postgres_version,
                "docker": _docker_version(),
                "cpu_count": os.cpu_count(),
                "memory_megabytes": _memory_megabytes(),
            },
            "configuration": {
                "base_url": base_url,
                "metric_batch_size": configured_batch_size,
                "clock_method": (
                    "perf_counter_ns for client phases; PostgreSQL timestamps "
                    "only for internal phase differences"
                ),
                "temporal_thresholds": None,
            },
            "expected_counts": expected,
            "actual_counts": asdict(counts),
            "metric_state_expected": expected_values,
            "metric_state_actual": actual_values,
            "errors": errors,
            "throughput_events_per_second": profile.events / elapsed_seconds,
            "drain_time_ms": (state_ready_ns - ingress_completed_ns) / 1_000_000,
            "maximum_backlog": maximum_backlog,
            "statistics": {
                "ingress": summarize_durations(ingress_latencies),
                "worker_wait": summarize_durations(phases["worker_wait_ms"]),
                "processing_plans": summarize_durations(phases["plans_ms"]),
                "observation_available": summarize_durations(phases["observation_ms"]),
                "metric_state_available": summarize_durations(phases["total_ms"]),
                "runtime_total": summarize_durations(total_client_ms),
            },
            "integrity": {"passed": not errors},
            "limitations": [
                "The API process and worker run on one host.",
                "One metric aggregator is exercised; concurrent aggregators are not claimed.",
                "Shared CI runners provide comparative data, not absolute capacity or an SLA.",
            ],
        }
        json_path, markdown_path = write_reports(report, output_directory)
        if errors:
            raise AssertionError("; ".join(errors))
        return report, json_path, markdown_path
    finally:
        if project_id is not None:
            _cleanup_scope(project_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--events", type=int, default=100)
    parser.add_argument("--payload-bytes", type=int, default=1024)
    parser.add_argument("--producers", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument(
        "--output-directory", type=Path, default=DEFAULT_OUTPUT_DIRECTORY
    )
    args = parser.parse_args()
    profile = BaselineProfile(
        events=args.events,
        payload_bytes=args.payload_bytes,
        producers=args.producers,
    )
    report, json_path, markdown_path = run_baseline(
        base_url=args.base_url,
        output_directory=args.output_directory,
        profile=profile,
        timeout_seconds=args.timeout_seconds,
    )
    print(
        json.dumps(
            {
                "integrity": report["integrity"],
                "json_report": str(json_path),
                "markdown_report": str(markdown_path),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
