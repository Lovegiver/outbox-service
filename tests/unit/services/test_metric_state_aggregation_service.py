from __future__ import annotations

import pytest

from app.models.analytical_observation import AnalyticalObservation
from app.models.metric_checkpoint import MetricCheckpoint
from app.repositories.metric_state_repository import (
    MetricObservationStream,
    MetricStateDelta,
    build_checkpoint_name,
)
from app.services.metric_state_aggregation_service import (
    MetricStateAggregationError,
    MetricStateAggregationService,
)


class FakeMetricStateRepository:
    def __init__(self, observations: list[AnalyticalObservation]) -> None:
        self.observations = observations
        self.checkpoints: dict[str, MetricCheckpoint] = {}
        self.values: dict[tuple[int, int, str, str], float] = {}

    def find_observation_streams(self) -> list[MetricObservationStream]:
        return [MetricObservationStream(project_id=1, event_type_id=2)]

    def get_or_create_checkpoint(self, checkpoint_name: str) -> MetricCheckpoint:
        return self.checkpoints.setdefault(
            checkpoint_name,
            MetricCheckpoint(
                checkpoint_name=checkpoint_name,
                last_processed_observation_id=0,
            ),
        )

    def find_observations_after(
        self,
        project_id: int,
        event_type_id: int,
        observation_id: int,
        limit: int = 1000,
    ) -> list[AnalyticalObservation]:
        return [
            observation
            for observation in self.observations
            if observation.project_id == project_id
            and observation.event_type_id == event_type_id
            and observation.id > observation_id
        ][:limit]

    def upsert_delta(self, delta: MetricStateDelta) -> None:
        key = (
            delta.project_id,
            delta.event_type_id,
            delta.metric_code,
            delta.labels_hash,
        )
        self.values[key] = self.values.get(key, 0) + delta.value

    def update_checkpoint(
        self,
        checkpoint: MetricCheckpoint,
        last_processed_observation_id: int,
    ) -> MetricCheckpoint:
        checkpoint.last_processed_observation_id = last_processed_observation_id
        return checkpoint

    def find_states_by_event_type(self, event_type_id: int) -> list:
        return []

    def find_all_states(self) -> list:
        return []


def _observation(
    observation_id: int,
    *,
    value: float,
    labels: dict | None = None,
) -> AnalyticalObservation:
    return AnalyticalObservation(
        id=observation_id,
        project_id=1,
        event_type_id=2,
        event_id=10,
        metric_definition_id=20,
        metric_definition_version_id=30,
        metric_code="products_sold_total",
        value=value,
        dimensions_json=labels or {},
    )


def test_aggregation_is_idempotent_without_new_observation() -> None:
    repository = FakeMetricStateRepository(
        [
            _observation(1, value=2, labels={"country": "FR"}),
            _observation(2, value=3, labels={"country": "FR"}),
        ]
    )
    service = MetricStateAggregationService(repository)

    assert service.aggregate_stream(project_id=1, event_type_id=2) == 2
    first_value = next(iter(repository.values.values()))

    assert service.aggregate_stream(project_id=1, event_type_id=2) == 0
    assert next(iter(repository.values.values())) == first_value == 5


def test_aggregation_advances_checkpoint_to_last_observation() -> None:
    repository = FakeMetricStateRepository(
        [_observation(7, value=1), _observation(9, value=1)]
    )
    service = MetricStateAggregationService(repository)

    service.aggregate_stream(project_id=1, event_type_id=2)

    checkpoint = repository.checkpoints[build_checkpoint_name(1, 2)]
    assert checkpoint.last_processed_observation_id == 9


def test_aggregation_processes_limited_batches_without_losing_observations() -> None:
    repository = FakeMetricStateRepository(
        [_observation(1, value=2), _observation(2, value=3)]
    )
    service = MetricStateAggregationService(repository)

    assert service.aggregate_stream(project_id=1, event_type_id=2, limit=1) == 1
    assert next(iter(repository.values.values())) == 2

    assert service.aggregate_stream(project_id=1, event_type_id=2, limit=1) == 1
    assert next(iter(repository.values.values())) == 5
    assert repository.checkpoints[
        build_checkpoint_name(1, 2)
    ].last_processed_observation_id == 2


def test_aggregation_rejects_reserved_business_label() -> None:
    repository = FakeMetricStateRepository(
        [_observation(1, value=1, labels={"ob1_project": "forged"})]
    )
    service = MetricStateAggregationService(repository)

    with pytest.raises(MetricStateAggregationError, match="reserved prefix"):
        service.aggregate_stream(project_id=1, event_type_id=2)

    assert repository.values == {}
    checkpoint = repository.checkpoints[build_checkpoint_name(1, 2)]
    assert checkpoint.last_processed_observation_id == 0


def test_aggregation_rejects_negative_counter_observation() -> None:
    repository = FakeMetricStateRepository([_observation(1, value=-1)])
    service = MetricStateAggregationService(repository)

    with pytest.raises(MetricStateAggregationError, match="negative"):
        service.aggregate_stream(project_id=1, event_type_id=2)

    assert repository.values == {}
