from __future__ import annotations

from typing import Protocol

from app.metrics_engine.compiled_processing_plan import CompiledProcessingPlan
from app.metrics_engine.event_scope import EventScope
from app.metrics_engine.observation_extractor import (
    extract_observations_from_compiled_plan,
)
from app.metrics_engine.persistable_observation import PersistableObservation
from app.models.analytical_observation import AnalyticalObservation
from app.models.event import Event


class AnalyticalObservationRepositoryProtocol(Protocol):
    def add_all(self, observations: list[AnalyticalObservation]) -> list[AnalyticalObservation]:
        ...

class ProcessingPlanProviderProtocol(Protocol):
    def get_active_plans(
        self,
        event_type_id: int,
        schema_definition_id: int,
    ) -> list[CompiledProcessingPlan]:
        ...


class MetricsExtractionService:
    def __init__(
            self,
            analytical_observation_repository: AnalyticalObservationRepositoryProtocol,
            processing_plan_provider: ProcessingPlanProviderProtocol,
    ) -> None:
        self.analytical_observation_repository = (
            analytical_observation_repository
        )

        self.processing_plan_provider = processing_plan_provider

    def extract_and_persist_for_event(
        self,
        event: Event,
    ) -> list[AnalyticalObservation]:

        compiled_plans = self.processing_plan_provider.get_active_plans(
            event_type_id=event.event_type_id,
            schema_definition_id=event.schema_definition_id,
        )

        persistable_observations: list[PersistableObservation] = []

        event_scope = EventScope(
            project_id=event.project_id,
            event_type_id=event.event_type_id,
            event_id=event.id,
        )

        for compiled_plan in compiled_plans:

            observations = extract_observations_from_compiled_plan(
                payload=event.payload,
                compiled_plan_json=compiled_plan.compiled_plan_json,
            )

            for observation in observations:
                persistable_observations.append(
                    PersistableObservation(
                        scope=event_scope,
                        metric_definition_id=(
                            compiled_plan.metric_definition_id
                        ),
                        metric_definition_version_id=(
                            compiled_plan.metric_definition_version_id
                        ),
                        observation=observation,
                    )
                )

        return self.persist_observations(
            persistable_observations
        )

    def persist_observations(
        self,
        observations: list[PersistableObservation],
    ) -> list[AnalyticalObservation]:

        analytical_observations = [
            self._to_analytical_observation(observation)
            for observation in observations
        ]

        return self.analytical_observation_repository.add_all(
            analytical_observations
        )

    def _to_analytical_observation(
        self,
        persistable_observation: PersistableObservation,
    ) -> AnalyticalObservation:

        return AnalyticalObservation(
            project_id=persistable_observation.scope.project_id,
            event_type_id=persistable_observation.scope.event_type_id,
            event_id=persistable_observation.scope.event_id,
            metric_definition_id=(
                persistable_observation.metric_definition_id
            ),
            metric_definition_version_id=(
                persistable_observation.metric_definition_version_id
            ),
            metric_code=(
                persistable_observation.observation.metric_code
            ),
            value=persistable_observation.observation.value,
            dimensions_json=(
                persistable_observation.observation.dimensions
            ),
        )