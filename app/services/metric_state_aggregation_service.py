from __future__ import annotations

from app.repositories.metric_state_repository import (
    MetricObservationStream,
    MetricStateDelta,
    build_checkpoint_name,
    build_labels_hash,
)
from collections import defaultdict
import math
from typing import Protocol, Optional

from app.metrics_engine.prometheus_renderer import (
    PrometheusRenderingError,
    normalize_business_labels,
)
from app.models.analytical_observation import AnalyticalObservation
from app.models.metric_checkpoint import MetricCheckpoint
from app.models.metric_state import MetricState


class MetricStateRepositoryProtocol(Protocol):
    def find_observation_streams(self) -> list[MetricObservationStream]:
        ...

    def get_or_create_checkpoint(self, checkpoint_name: str) -> MetricCheckpoint:
        ...

    def find_observations_after(
        self,
        project_id: int,
        event_type_id: int,
        observation_id: int,
        limit: int = 1000,
    ) -> list[AnalyticalObservation]:
        ...

    def upsert_delta(self, delta: MetricStateDelta) -> None:
        ...

    def update_checkpoint(
        self,
        checkpoint: MetricCheckpoint,
        last_processed_observation_id: int,
    ) -> MetricCheckpoint:
        ...

    def find_states_by_event_type(self, event_type_id: int) -> list[MetricState]:
        ...

    def find_all_states(self) -> list[MetricState]:
        ...


class MetricStateAggregationError(ValueError):
    """Raised when observations cannot form a valid counter state."""


class MetricStateAggregationService:
    """
    Aggregate AnalyticalObservation rows into Prometheus-ready MetricState rows.

    This service is the bridge between the analytical observation log and the
    /metrics endpoint. It processes observations incrementally using a durable
    checkpoint per project/EventType stream so that counters are not recalculated
    during Prometheus scrapes.
    """

    def __init__(
        self,
        metric_state_repository: MetricStateRepositoryProtocol,
    ) -> None:
        self.metric_state_repository = metric_state_repository

    def aggregate_all_streams(
        self,
        limit_per_stream: int = 1000,
    ) -> int:
        """
        Aggregate pending observations for every known project/EventType stream.

        Args:
            limit_per_stream: Maximum observations to aggregate per stream.

        Returns:
            Total number of observations consumed across all streams.
        """

        total_count = 0

        for stream in self.metric_state_repository.find_observation_streams():
            total_count += self.aggregate_stream(
                project_id=stream.project_id,
                event_type_id=stream.event_type_id,
                limit=limit_per_stream,
            )

        return total_count

    def find_observation_streams(self) -> list[MetricObservationStream]:
        """Return the independent streams currently awaiting aggregation."""

        return self.metric_state_repository.find_observation_streams()

    def aggregate_stream(
        self,
        project_id: int,
        event_type_id: int,
        limit: int = 1000,
    ) -> int:
        """
        Aggregate one project/EventType observation stream into MetricState.

        Args:
            project_id: Project owning the stream.
            event_type_id: EventType owning the stream.
            limit: Maximum number of observations to aggregate.

        Returns:
            Number of observations consumed for the stream.
        """

        checkpoint = self.metric_state_repository.get_or_create_checkpoint(
            checkpoint_name=build_checkpoint_name(
                project_id=project_id,
                event_type_id=event_type_id,
            ),
        )

        observations = self.metric_state_repository.find_observations_after(
            project_id=project_id,
            event_type_id=event_type_id,
            observation_id=checkpoint.last_processed_observation_id,
            limit=limit,
        )

        if not observations:
            return 0

        self._validate_observation_batch(
            observations=observations,
            project_id=project_id,
            event_type_id=event_type_id,
            checkpoint_observation_id=(
                checkpoint.last_processed_observation_id
            ),
        )
        deltas = self._aggregate_observations(observations)

        for delta in deltas:
            self.metric_state_repository.upsert_delta(delta)

        self.metric_state_repository.update_checkpoint(
            checkpoint=checkpoint,
            last_processed_observation_id=observations[-1].id,
        )

        return len(observations)

    def find_states_by_event_type(
        self,
        event_type_id: int,
    ) -> list[MetricState]:
        """
        Return materialized Prometheus metric states for one EventType.

        Args:
            event_type_id: EventType identifier requested by Prometheus.

        Returns:
            Current metric state rows for the EventType.
        """

        return self.metric_state_repository.find_states_by_event_type(
            event_type_id=event_type_id,
        )

    def find_all_states(self) -> list[MetricState]:
        """
        Return all materialized Prometheus metric states.

        Returns:
            Current metric state rows.
        """

        return self.metric_state_repository.find_all_states()

    def _aggregate_observations(
        self,
        observations: list[AnalyticalObservation],
    ) -> list[MetricStateDelta]:
        """
        Collapse raw observations into one delta per metric series.

        Args:
            observations: Analytical observations loaded after the checkpoint.

        Returns:
            Summed deltas grouped by project, event type, metric code and labels.
        """

        grouped: dict[tuple[int, int, str, str], MetricStateDelta] = {}
        values: defaultdict[tuple[int, int, str, str], float] = defaultdict(float)

        for observation in observations:
            labels = self._normalize_labels(observation.dimensions_json)
            value = self._normalize_counter_value(observation)
            labels_hash = build_labels_hash(labels)
            key = (
                observation.project_id,
                observation.event_type_id,
                observation.metric_code,
                labels_hash,
            )

            values[key] += value

            if key not in grouped:
                grouped[key] = MetricStateDelta(
                    project_id=observation.project_id,
                    event_type_id=observation.event_type_id,
                    metric_definition_id=observation.metric_definition_id,
                    metric_definition_version_id=(
                        observation.metric_definition_version_id
                    ),
                    metric_code=observation.metric_code,
                    labels_json=labels,
                    labels_hash=labels_hash,
                    value=0.0,
                )

        return [
            MetricStateDelta(
                project_id=delta.project_id,
                event_type_id=delta.event_type_id,
                metric_definition_id=delta.metric_definition_id,
                metric_definition_version_id=delta.metric_definition_version_id,
                metric_code=delta.metric_code,
                labels_json=delta.labels_json,
                labels_hash=delta.labels_hash,
                value=values[key],
            )
            for key, delta in grouped.items()
        ]

    def _normalize_labels(
        self,
        labels: Optional[dict],
    ) -> dict[str, str]:
        """
        Convert observation dimensions into Prometheus label strings.

        Args:
            labels: Raw JSONB dimensions from AnalyticalObservation.

        Returns:
            Deterministically ordered string labels.
        """

        try:
            return normalize_business_labels(labels)
        except PrometheusRenderingError as exc:
            raise MetricStateAggregationError(str(exc)) from exc

    @staticmethod
    def _normalize_counter_value(
        observation: AnalyticalObservation,
    ) -> float:
        try:
            value = float(observation.value)
        except (TypeError, ValueError) as exc:
            raise MetricStateAggregationError(
                f"Observation {observation.id} has a non-numeric counter value."
            ) from exc

        if not math.isfinite(value):
            raise MetricStateAggregationError(
                f"Observation {observation.id} has a non-finite counter value."
            )

        if value < 0:
            raise MetricStateAggregationError(
                f"Observation {observation.id} has a negative counter value."
            )

        return value

    @staticmethod
    def _validate_observation_batch(
        observations: list[AnalyticalObservation],
        project_id: int,
        event_type_id: int,
        checkpoint_observation_id: int,
    ) -> None:
        previous_id = checkpoint_observation_id

        for observation in observations:
            if (
                observation.project_id != project_id
                or observation.event_type_id != event_type_id
            ):
                raise MetricStateAggregationError(
                    "Observation batch contains an item outside its "
                    "Project/EventType stream."
                )

            if observation.id is None or observation.id <= previous_id:
                raise MetricStateAggregationError(
                    "Observation batch is not strictly ordered after its checkpoint."
                )

            previous_id = observation.id
