from __future__ import annotations

from app.metrics_engine.observation_extractor import (
    extract_keyed_observations_from_compiled_plan,
)
from app.models.analytical_observation import AnalyticalObservation
from app.models.event import Event
from app.models.metric_plan_execution import MetricPlanExecution
from app.models.processing_plan import ProcessingPlan


class MetricsExtractionService:
    """Pure mapper from one persisted compiled plan to traceable observations."""

    def extract_for_plan(
        self,
        *,
        event: Event,
        plan: ProcessingPlan,
        execution: MetricPlanExecution,
    ) -> list[AnalyticalObservation]:
        """Execute the compiled document without configuration-time services."""
        if plan.compiled_plan_json is None:
            raise ValueError(f"ProcessingPlan {plan.id} has no compiled document")

        return [
            AnalyticalObservation(
                project_id=event.project_id,
                event_type_id=event.event_type_id,
                event_id=event.id,
                metric_definition_id=plan.metric_definition_id,
                metric_definition_version_id=plan.metric_definition_version_id,
                processing_chain_id=execution.processing_chain_id,
                processing_plan_id=plan.id,
                metric_plan_execution_id=execution.id,
                observation_key=item.observation_key,
                metric_code=item.observation.metric_code,
                value=item.observation.value,
                dimensions_json=item.observation.dimensions,
            )
            for item in extract_keyed_observations_from_compiled_plan(
                payload=event.payload,
                compiled_plan_json=plan.compiled_plan_json,
            )
        ]
