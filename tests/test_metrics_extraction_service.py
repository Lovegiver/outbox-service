from app.metrics_engine.event_scope import EventScope
from app.metrics_engine.observation import Observation
from app.metrics_engine.persistable_observation import PersistableObservation
from app.services.metrics_extraction_service import MetricsExtractionService


class FakeAnalyticalObservationRepository:
    def add_all(self, observations):
        return observations


class FakeProcessingPlanProvider:
    def get_active_plans(self, event_type_id, schema_definition_id):
        return []


def test_persist_observations_maps_runtime_observation_to_analytical_observation() -> None:
    service = MetricsExtractionService(
        analytical_observation_repository=FakeAnalyticalObservationRepository(),
        processing_plan_provider=FakeProcessingPlanProvider(),
    )

    persistable_observation = PersistableObservation(
        scope=EventScope(
            project_id=1,
            event_type_id=2,
            event_id=3,
        ),
        metric_definition_id=4,
        metric_definition_version_id=5,
        observation=Observation(
            metric_code="duration_seconds",
            value=28.0,
            dimensions={
                "step_name": "extract",
                "step_index": 0,
            },
        ),
    )

    result = service.persist_observations([persistable_observation])

    assert len(result) == 1

    analytical_observation = result[0]

    assert analytical_observation.project_id == 1
    assert analytical_observation.event_type_id == 2
    assert analytical_observation.event_id == 3
    assert analytical_observation.metric_definition_id == 4
    assert analytical_observation.metric_definition_version_id == 5
    assert analytical_observation.metric_code == "duration_seconds"
    assert analytical_observation.value == 28.0
    assert analytical_observation.dimensions_json == {
        "step_name": "extract",
        "step_index": 0,
    }