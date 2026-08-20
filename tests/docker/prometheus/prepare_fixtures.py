from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.database import engine
from tests.domain.persisted_object import PersistedProject
from tests.domain.record import (
    AnalyticalObservationRecord,
    EventRecord,
    EventTypeRecord,
    MetricDefinitionRecord,
    MetricDefinitionVersionRecord,
    ProjectRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.object_factory import ObjectFactory


def _create_observation_stream(
    factory: ObjectFactory,
    project: PersistedProject,
    event_type_code: str,
    metric_code: str,
    observations: list[tuple[float, dict[str, str]]],
) -> None:
    """Create one stream of observations without materializing MetricState."""

    event_type = factory.event_type(
        EventTypeRecord(
            project=project,
            code=event_type_code,
            name=event_type_code,
        )
    )
    schema = factory.schema_definition(
        SchemaDefinitionRecord(event_type=event_type)
    )
    event = factory.event(
        EventRecord(
            event_type=event_type,
            schema_definition=schema,
            payload={"source": "docker-prometheus-integration"},
            status="ROUTED",
        )
    )
    metric_definition = factory.metric_definition(
        MetricDefinitionRecord(
            event_type=event_type,
            code=metric_code,
            name=metric_code,
        )
    )
    metric_version = factory.metric_definition_version(
        MetricDefinitionVersionRecord(
            metric_definition=metric_definition,
        )
    )

    for value, labels in observations:
        factory.analytical_observation(
            AnalyticalObservationRecord(
                event=event,
                metric_definition=metric_definition,
                metric_definition_version=metric_version,
                metric_code=metric_code,
                value=value,
                dimensions_json=labels,
            )
        )


def prepare_fixtures() -> dict[str, Any]:
    """Persist deterministic observations and return their public contract."""

    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project_a = factory.project(ProjectRecord(name="docker-shop-a"))
        project_b = factory.project(ProjectRecord(name="docker-shop-b"))

        _create_observation_stream(
            factory=factory,
            project=project_a,
            event_type_code="product.sold",
            metric_code="products_sold_total",
            observations=[
                (7, {"country": "FR"}),
                (5, {"country": "FR"}),
            ],
        )
        _create_observation_stream(
            factory=factory,
            project=project_a,
            event_type_code="product.returned",
            metric_code="products_returned_total",
            observations=[(2, {"reason": "damaged"})],
        )
        _create_observation_stream(
            factory=factory,
            project=project_b,
            event_type_code="order.created",
            metric_code="orders_created_total",
            observations=[(4, {"region": "west"})],
        )

    return {
        "projects": [
            {
                "id": project_a.id,
                "name": project_a.name,
                "metrics_path": (
                    f"/metrics/projects/{project_a.id}/prometheus-state"
                ),
                "expected_metric_names": [
                    "ob1_products_sold_total",
                    "ob1_products_returned_total",
                ],
                "forbidden_metric_names": ["ob1_orders_created_total"],
            },
            {
                "id": project_b.id,
                "name": project_b.name,
                "metrics_path": (
                    f"/metrics/projects/{project_b.id}/prometheus-state"
                ),
                "expected_metric_names": ["ob1_orders_created_total"],
                "forbidden_metric_names": [
                    "ob1_products_sold_total",
                    "ob1_products_returned_total",
                ],
            },
        ],
        "series": [
            {
                "metric_name": "ob1_products_sold_total",
                "value": 12,
                "labels": {
                    "country": "FR",
                    "ob1_event_type": "product.sold",
                    "ob1_project": "docker-shop-a",
                },
            },
            {
                "metric_name": "ob1_products_returned_total",
                "value": 2,
                "labels": {
                    "reason": "damaged",
                    "ob1_event_type": "product.returned",
                    "ob1_project": "docker-shop-a",
                },
            },
            {
                "metric_name": "ob1_orders_created_total",
                "value": 4,
                "labels": {
                    "region": "west",
                    "ob1_event_type": "order.created",
                    "ob1_project": "docker-shop-b",
                },
            },
        ],
    }


def main() -> None:
    """Create fixtures and generate file-SD targets from actual Project ids."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--targets-file", required=True, type=Path)
    parser.add_argument("--fixtures-file", required=True, type=Path)
    args = parser.parse_args()

    fixture_contract = prepare_fixtures()
    targets = [
        {
            "targets": ["app:8000"],
            "labels": {
                "__metrics_path__": project["metrics_path"],
                "fixture_project": project["name"],
            },
        }
        for project in fixture_contract["projects"]
    ]

    args.targets_file.parent.mkdir(parents=True, exist_ok=True)
    args.targets_file.write_text(
        json.dumps(targets, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.fixtures_file.write_text(
        json.dumps(fixture_contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "Prepared Prometheus fixtures for Projects "
        + ", ".join(
            f'{project["name"]}={project["id"]}'
            for project in fixture_contract["projects"]
        )
    )


if __name__ == "__main__":
    main()
