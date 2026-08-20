from types import SimpleNamespace

from app import worker
from app.repositories.metric_state_repository import MetricObservationStream
from app.services.metric_state_aggregation_service import (
    MetricStateAggregationError,
)


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.close_count += 1


class FakeAggregationService:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int]] = []

    def find_observation_streams(self) -> list[MetricObservationStream]:
        return [
            MetricObservationStream(project_id=1, event_type_id=10),
            MetricObservationStream(project_id=1, event_type_id=20),
        ]

    def aggregate_stream(
        self,
        project_id: int,
        event_type_id: int,
        limit: int,
    ) -> int:
        self.calls.append((project_id, event_type_id))
        if event_type_id == 10:
            raise MetricStateAggregationError("invalid stream")
        return 3


def test_worker_commits_and_rolls_back_each_stream_independently(
    monkeypatch,
) -> None:
    session = FakeSession()
    service = FakeAggregationService()
    factory = SimpleNamespace(
        create_metric_state_aggregation_service=lambda db: service,
    )
    monkeypatch.setattr(worker, "SessionLocal", lambda: session)
    monkeypatch.setattr(worker, "ServiceFactory", factory)

    result = worker.aggregate_prometheus_metric_state()

    assert service.calls == [(1, 10), (1, 20)]
    assert session.rollback_count == 1
    assert session.commit_count == 1
    assert session.close_count == 1
    assert result.aggregated_count == 3
    assert len(result.failures) == 1
    assert isinstance(result.failures[0].error, MetricStateAggregationError)
