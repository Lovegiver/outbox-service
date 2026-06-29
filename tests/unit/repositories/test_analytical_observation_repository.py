from app.models.analytical_observation import AnalyticalObservation
from app.repositories.analytical_observation_repository import (
    AnalyticalObservationRepository,
)


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.added_all = []
        self.flushed = False

    def add(self, instance) -> None:
        self.added.append(instance)

    def add_all(self, instances) -> None:
        self.added_all.extend(instances)

    def flush(self) -> None:
        self.flushed = True


def test_add_persists_and_flushes_observation() -> None:
    session = FakeSession()
    repository = AnalyticalObservationRepository(session)

    observation = AnalyticalObservation(
        project_id=1,
        event_type_id=1,
        event_id=1,
        metric_definition_id=1,
        metric_definition_version_id=1,
        metric_code="duration_seconds",
        value=28.0,
        dimensions_json={"step_name": "extract", "step_index": 0},
    )

    result = repository.add(observation)

    assert result is observation
    assert session.added == [observation]
    assert session.flushed is True


def test_add_all_persists_and_flushes_observations() -> None:
    session = FakeSession()
    repository = AnalyticalObservationRepository(session)

    observations = [
        AnalyticalObservation(
            project_id=1,
            event_type_id=1,
            event_id=1,
            metric_definition_id=1,
            metric_definition_version_id=1,
            metric_code="duration_seconds",
            value=28.0,
            dimensions_json={"step_name": "extract", "step_index": 0},
        ),
        AnalyticalObservation(
            project_id=1,
            event_type_id=1,
            event_id=1,
            metric_definition_id=1,
            metric_definition_version_id=1,
            metric_code="tokens_per_second",
            value=42.5,
            dimensions_json={"phase": "prompt"},
        ),
    ]

    result = repository.add_all(observations)

    assert result == observations
    assert session.added_all == observations
    assert session.flushed is True