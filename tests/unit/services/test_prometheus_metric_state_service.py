from types import SimpleNamespace

import pytest

from app.repositories.metric_state_repository import PrometheusMetricStateRow
from app.services.prometheus_metric_state_service import (
    PrometheusMetricStateService,
    PrometheusMetricStateStructureError,
    PrometheusProjectNotFoundError,
)


class FakeProjectRepository:
    def __init__(self, project) -> None:
        self.project = project

    def find_by_id(self, project_id: int):
        if self.project is not None and self.project.id == project_id:
            return self.project
        return None


class FakeMetricStateRepository:
    def __init__(self, rows: list[PrometheusMetricStateRow]) -> None:
        self.rows = rows
        self.requested_project_ids: list[int] = []

    def find_prometheus_rows_by_project(
        self,
        project_id: int,
    ) -> list[PrometheusMetricStateRow]:
        self.requested_project_ids.append(project_id)
        return self.rows


def _row(**overrides) -> PrometheusMetricStateRow:
    values = {
        "state_id": 1,
        "project_id": 10,
        "event_type_id": 20,
        "event_type_project_id": 10,
        "event_type_code": "product.sold",
        "metric_code": "products_sold_total",
        "labels_json": {"country": "FR"},
        "value": 12,
    }
    values.update(overrides)
    return PrometheusMetricStateRow(**values)


def test_service_returns_404_domain_error_before_loading_states() -> None:
    state_repository = FakeMetricStateRepository([])
    service = PrometheusMetricStateService(
        project_repository=FakeProjectRepository(None),
        metric_state_repository=state_repository,
    )

    with pytest.raises(PrometheusProjectNotFoundError):
        service.render_project(10)

    assert state_repository.requested_project_ids == []


def test_service_renders_joined_project_state() -> None:
    service = PrometheusMetricStateService(
        project_repository=FakeProjectRepository(
            SimpleNamespace(id=10, name="shop")
        ),
        metric_state_repository=FakeMetricStateRepository([_row()]),
    )

    document = service.render_project(10)

    assert 'ob1_project="shop"' in document
    assert 'ob1_event_type="product.sold"' in document
    assert document.endswith(" 12\n")


def test_service_rejects_event_type_from_another_project() -> None:
    service = PrometheusMetricStateService(
        project_repository=FakeProjectRepository(
            SimpleNamespace(id=10, name="shop")
        ),
        metric_state_repository=FakeMetricStateRepository(
            [_row(event_type_project_id=11)]
        ),
    )

    with pytest.raises(PrometheusMetricStateStructureError, match="another Project"):
        service.render_project(10)
