from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import text

from app.database import engine


APP_BASE_URL = "http://app:8000"
PROMETHEUS_BASE_URL = "http://prometheus:9090"
POLL_INTERVAL_SECONDS = 2
WAIT_TIMEOUT_SECONDS = 90


def _request_text(url: str) -> tuple[str, str]:
    request = Request(url=url, headers={"Accept": "text/plain"})
    with urlopen(request, timeout=5) as response:
        body = response.read().decode("utf-8")
        return body, response.headers.get("Content-Type", "")


def _request_json(url: str) -> dict[str, Any]:
    request = Request(url=url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_until(
    description: str,
    probe: Callable[[], tuple[bool, Any]],
) -> Any:
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
    last_result: Any = None
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            complete, last_result = probe()
            if complete:
                return last_result
        except Exception as exc:  # Diagnostics retain the last bounded error.
            last_error = exc

        time.sleep(POLL_INTERVAL_SECONDS)

    raise AssertionError(
        f"Timed out after {WAIT_TIMEOUT_SECONDS}s waiting for {description}. "
        f"Last result={last_result!r}; last error={last_error!r}"
    )


def _database_snapshot() -> dict[str, list[list[Any]]]:
    with engine.connect() as connection:
        checkpoints = connection.execute(
            text(
                """
                SELECT checkpoint_name, last_processed_observation_id
                FROM outbox.metric_checkpoint
                ORDER BY checkpoint_name
                """
            )
        ).all()
        states = connection.execute(
            text(
                """
                SELECT project_id, event_type_id, metric_code, labels_hash, value
                FROM outbox.metric_state
                ORDER BY project_id, event_type_id, metric_code, labels_hash
                """
            )
        ).all()

    return {
        "checkpoints": [list(row) for row in checkpoints],
        "states": [list(row) for row in states],
    }


def _expected_line(series: dict[str, Any]) -> str:
    labels = ",".join(
        f'{name}="{value}"'
        for name, value in sorted(series["labels"].items())
    )
    return f'{series["metric_name"]}{{{labels}}} {series["value"]}'


def _promql(series: dict[str, Any]) -> str:
    labels = ",".join(
        f'{name}="{value}"'
        for name, value in sorted(series["labels"].items())
    )
    return f'{series["metric_name"]}{{{labels}}}'


def _query_prometheus(query: str) -> dict[str, Any]:
    url = f"{PROMETHEUS_BASE_URL}/api/v1/query?{urlencode({'query': query})}"
    return _request_json(url)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Verify a real scrape from OB1 through Prometheus and PromQL."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-file", required=True, type=Path)
    parser.add_argument("--artifact-directory", required=True, type=Path)
    args = parser.parse_args()
    args.artifact_directory.mkdir(parents=True, exist_ok=True)

    fixtures = json.loads(args.fixtures_file.read_text(encoding="utf-8"))
    series_by_project = {
        project["name"]: [
            series
            for series in fixtures["series"]
            if series["labels"]["ob1_project"] == project["name"]
        ]
        for project in fixtures["projects"]
    }

    def endpoint_probe() -> tuple[bool, dict[str, str]]:
        documents: dict[str, str] = {}
        for project in fixtures["projects"]:
            body, content_type = _request_text(
                f'{APP_BASE_URL}{project["metrics_path"]}'
            )
            if not content_type.startswith(
                "text/plain; version=0.0.4; charset=utf-8"
            ):
                return False, {
                    "project": project["name"],
                    "content_type": content_type,
                    "body": body,
                }
            documents[project["name"]] = body

            for series in series_by_project[project["name"]]:
                if _expected_line(series) not in body:
                    return False, documents

        return True, documents

    endpoint_documents = _wait_until(
        "the worker to materialize all endpoint series",
        endpoint_probe,
    )

    snapshot_before_get = _database_snapshot()
    endpoint_documents = endpoint_probe()[1]
    snapshot_after_get = _database_snapshot()
    assert snapshot_before_get == snapshot_after_get, (
        "Prometheus endpoint GET changed MetricState or MetricCheckpoint."
    )

    for project in fixtures["projects"]:
        body = endpoint_documents[project["name"]]
        for metric_name in project["expected_metric_names"]:
            assert metric_name in body
        for metric_name in project["forbidden_metric_names"]:
            assert metric_name not in body
        (args.artifact_directory / f'endpoint-{project["name"]}.txt').write_text(
            body,
            encoding="utf-8",
        )

    _wait_until(
        "Prometheus readiness",
        lambda: (
            _request_text(f"{PROMETHEUS_BASE_URL}/-/ready")[0].strip()
            == "Prometheus Server is Ready.",
            _request_text(f"{PROMETHEUS_BASE_URL}/-/ready")[0],
        ),
    )

    expected_scrape_urls = {
        f'http://app:8000{project["metrics_path"]}'
        for project in fixtures["projects"]
    }

    def targets_probe() -> tuple[bool, dict[str, Any]]:
        response = _request_json(f"{PROMETHEUS_BASE_URL}/api/v1/targets")
        active_targets = response.get("data", {}).get("activeTargets", [])
        targets = {
            target.get("scrapeUrl"): target.get("health")
            for target in active_targets
        }
        complete = all(
            targets.get(scrape_url) == "up"
            for scrape_url in expected_scrape_urls
        )
        return complete, response

    targets_response = _wait_until(
        "all expected Prometheus targets to become UP",
        targets_probe,
    )
    _write_json(args.artifact_directory / "targets.json", targets_response)

    promql_responses: dict[str, Any] = {}
    for series in fixtures["series"]:
        query = _promql(series)

        def query_probe() -> tuple[bool, dict[str, Any]]:
            response = _query_prometheus(query)
            result = response.get("data", {}).get("result", [])
            complete = (
                response.get("status") == "success"
                and len(result) == 1
                and float(result[0]["value"][1]) == float(series["value"])
                and all(
                    result[0]["metric"].get(name) == value
                    for name, value in series["labels"].items()
                )
            )
            return complete, response

        promql_responses[query] = _wait_until(
            f"PromQL result for {query}",
            query_probe,
        )

    isolation_queries = [
        'ob1_products_sold_total{ob1_project="docker-shop-b"}',
        'ob1_orders_created_total{ob1_project="docker-shop-a"}',
    ]
    for query in isolation_queries:
        response = _query_prometheus(query)
        assert response.get("status") == "success"
        assert response.get("data", {}).get("result", []) == []
        promql_responses[query] = response

    _write_json(
        args.artifact_directory / "promql-responses.json",
        promql_responses,
    )
    _write_json(
        args.artifact_directory / "database-snapshot.json",
        snapshot_after_get,
    )
    print(
        "Prometheus integration verified: 2 Projects, 2 UP targets, "
        "3 exact business series, endpoint and PromQL isolation."
    )


if __name__ == "__main__":
    main()
