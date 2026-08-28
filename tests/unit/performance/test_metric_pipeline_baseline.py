"""Unit tests for deterministic metric baseline calculations."""

from __future__ import annotations

import json

import pytest

from tests.performance.metric_pipeline_baseline import (
    BaselineProfile,
    PipelineCounts,
    expected_pipeline_counts,
    percentile,
    summarize_durations,
    validate_profile,
    wait_for_pipeline_completion,
    write_reports,
)


def test_expected_counts_do_not_mutate_profile() -> None:
    profile = BaselineProfile(events=30, plans=5)

    counts = expected_pipeline_counts(profile)

    assert counts == {
        "events": 30,
        "executions": 150,
        "observations": 150,
        "deliveries": 30,
        "metric_states": 5,
    }
    assert profile == BaselineProfile(events=30, plans=5)


def test_profile_requires_real_single_worker_batch_configuration() -> None:
    validate_profile(BaselineProfile(), configured_batch_size=100)

    with pytest.raises(ValueError, match="exactly one metric worker"):
        validate_profile(
            BaselineProfile(metric_workers=2),
            configured_batch_size=100,
        )
    with pytest.raises(ValueError, match="match the application configuration"):
        validate_profile(BaselineProfile(), configured_batch_size=50)


@pytest.mark.parametrize(
    ("quantile", "expected"),
    [(0.0, 1.0), (0.5, 2.5), (0.95, 3.85), (0.99, 3.97), (1.0, 4.0)],
)
def test_percentile_is_deterministic(quantile: float, expected: float) -> None:
    assert percentile([4.0, 1.0, 3.0, 2.0], quantile) == pytest.approx(expected)


def test_summary_has_no_temporal_pass_fail_threshold() -> None:
    summary = summarize_durations([1000.0, 1.0, 10.0])

    assert set(summary) == {"median_ms", "p95_ms", "p99_ms", "max_ms"}
    assert "threshold" not in summary


def test_completion_poll_detects_backlog_and_exact_terminal_state() -> None:
    samples = iter(
        (
            PipelineCounts(3, 3, 0, 0, 0, 0, 0),
            PipelineCounts(3, 0, 6, 6, 3, 8, 8),
        )
    )
    clock = iter((0, 1, 2, 3, 4))

    counts, maximum_backlog = wait_for_pipeline_completion(
        lambda: next(samples),
        expected={"events": 3, "executions": 6, "observations": 6, "deliveries": 3},
        timeout_seconds=1,
        poll_interval_seconds=0,
        monotonic_ns=lambda: next(clock),
        wait=lambda _seconds: None,
    )

    assert counts.terminal_executions == 6
    assert maximum_backlog == 9


def test_completion_timeout_reports_last_durable_counts() -> None:
    counts = PipelineCounts(1, 1, 0, 0, 0, 0, 0)
    clock = iter((0, 2_000_000_000))

    with pytest.raises(TimeoutError, match="received_events.*1"):
        wait_for_pipeline_completion(
            lambda: counts,
            expected={"events": 1, "executions": 5, "observations": 5, "deliveries": 1},
            timeout_seconds=1,
            poll_interval_seconds=0,
            monotonic_ns=lambda: next(clock),
            wait=lambda _seconds: None,
        )


def test_reports_serialize_json_and_markdown_without_generated_source(tmp_path) -> None:
    report = {
        "run_id": "unit",
        "commit_sha": "abc123",
        "profile": {"events": 100, "plans": 5},
        "throughput_events_per_second": 12.5,
        "statistics": {
            "ingress": {"median_ms": 1.0, "p95_ms": 2.0, "p99_ms": 3.0},
            "runtime_total": {"median_ms": 4.0, "p95_ms": 5.0, "p99_ms": 6.0},
        },
        "drain_time_ms": 7.0,
        "maximum_backlog": 500,
        "integrity": {"passed": True},
    }

    json_path, markdown_path = write_reports(report, tmp_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["run_id"] == "unit"
    assert "not an SLA" in markdown_path.read_text(encoding="utf-8")
