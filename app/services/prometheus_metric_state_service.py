from __future__ import annotations

from typing import Protocol

from app.metrics_engine.prometheus_renderer import (
    PrometheusMetricStateSample,
    render_prometheus_metric_states,
)
from app.models.project import Project
from app.repositories.metric_state_repository import PrometheusMetricStateRow


class ProjectRepositoryProtocol(Protocol):
    def find_by_id(self, project_id: int) -> Project | None:
        ...


class PrometheusMetricStateRepositoryProtocol(Protocol):
    def find_prometheus_rows_by_project(
        self,
        project_id: int,
    ) -> list[PrometheusMetricStateRow]:
        ...


class PrometheusProjectNotFoundError(LookupError):
    """Raised when the requested Project does not exist."""


class PrometheusMetricStateStructureError(RuntimeError):
    """Raised when persisted MetricState relationships are inconsistent."""


class PrometheusMetricStateService:
    """Read and render already-materialized counters for one Project."""

    def __init__(
        self,
        project_repository: ProjectRepositoryProtocol,
        metric_state_repository: PrometheusMetricStateRepositoryProtocol,
    ) -> None:
        self.project_repository = project_repository
        self.metric_state_repository = metric_state_repository

    def render_project(self, project_id: int) -> str:
        """
        Return the Prometheus document for one Project without side effects.

        This method never reads Events or AnalyticalObservations and never
        invokes the aggregation service.
        """

        project = self.project_repository.find_by_id(project_id)

        if project is None:
            raise PrometheusProjectNotFoundError(
                f"Project {project_id} not found."
            )

        rows = self.metric_state_repository.find_prometheus_rows_by_project(
            project_id=project_id,
        )

        samples: list[PrometheusMetricStateSample] = []

        for row in rows:
            if row.project_id != project_id:
                raise PrometheusMetricStateStructureError(
                    f"MetricState {row.state_id} belongs to an unexpected Project."
                )

            if row.event_type_project_id != project_id:
                raise PrometheusMetricStateStructureError(
                    f"MetricState {row.state_id} references an EventType from "
                    "another Project."
                )

            samples.append(
                PrometheusMetricStateSample(
                    metric_code=row.metric_code,
                    value=row.value,
                    business_labels=row.labels_json,
                    project_name=project.name,
                    event_type_code=row.event_type_code,
                )
            )

        return render_prometheus_metric_states(samples)
