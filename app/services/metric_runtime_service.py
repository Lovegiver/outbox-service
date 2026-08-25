from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable

from sqlalchemy.orm import Session

from app.core.metric_execution_status import (
    MetricPlanExecutionStatus,
    MetricProcessingStatus,
)
from app.metrics_engine.observation_extractor import ObservationExtractionError
from app.models.event import Event
from app.models.metric_plan_execution import MetricPlanExecution
from app.models.metric_processing_execution import MetricProcessingExecution
from app.repositories.analytical_observation_repository import (
    AnalyticalObservationRepository,
)
from app.repositories.event_repository import EventRepository
from app.repositories.metric_execution_repository import MetricExecutionRepository
from app.repositories.processing_plan_repository import ProcessingPlanRepository
from app.services.metrics_extraction_service import MetricsExtractionService
from app.services.processing_plan_provider import (
    ProcessingPlanConfigurationError,
    ProcessingPlanProvider,
)


@dataclass(frozen=True)
class MetricPlanExecutionResult:
    """Observable result of one isolated plan transaction."""

    execution_id: int
    status: str
    observation_count: int
    error: str | None = None


class MetricExecutionMaterializationService:
    """Freeze the exact active metric snapshot before routing an Event."""

    def __init__(
        self,
        processing_plan_provider: ProcessingPlanProvider,
        metric_execution_repository: MetricExecutionRepository,
    ) -> None:
        self.processing_plan_provider = processing_plan_provider
        self.metric_execution_repository = metric_execution_repository

    def materialize_for_event(self, event: Event) -> MetricProcessingExecution | None:
        """Create durable Event/plan orders once and preserve them on retries."""
        existing = self.metric_execution_repository.find_processing_by_event_id(
            event.id
        )
        if existing is not None:
            return existing

        try:
            snapshot = self.processing_plan_provider.get_active_snapshot(
                event_type_id=event.event_type_id,
                schema_definition_id=event.schema_definition_id,
            )
        except ProcessingPlanConfigurationError as exc:
            processing = self.metric_execution_repository.create_processing_if_absent(
                event_id=event.id,
                processing_chain_id=exc.processing_chain_id,
                status=MetricProcessingStatus.FAILED_CONFIGURATION,
                last_error=str(exc)[:2000],
            )
            if exc.processing_plan_id is not None:
                self.metric_execution_repository.create_failed_plan_execution_if_absent(
                    metric_processing_execution_id=processing.id,
                    event_id=event.id,
                    processing_chain_id=exc.processing_chain_id,
                    processing_plan_id=exc.processing_plan_id,
                    last_error=str(exc),
                )
            return processing

        if snapshot is None:
            return None

        if (
            event.event_type.project_id != event.project_id
            or event.schema_definition.event_type_id != event.event_type_id
            or event.schema_definition.json_version_internal
            != event.json_version_internal
        ):
            return self.metric_execution_repository.create_processing_if_absent(
                event_id=event.id,
                processing_chain_id=snapshot.processing_chain_id,
                status=MetricProcessingStatus.FAILED_CONFIGURATION,
                last_error="Event scope does not match its exact SchemaDefinition",
            )

        processing = self.metric_execution_repository.create_processing_if_absent(
            event_id=event.id,
            processing_chain_id=snapshot.processing_chain_id,
            status=MetricProcessingStatus.MATERIALIZED,
        )
        if processing.processing_chain_id != snapshot.processing_chain_id:
            return processing

        self.metric_execution_repository.create_plan_executions_if_absent(
            metric_processing_execution_id=processing.id,
            event_id=event.id,
            processing_chain_id=snapshot.processing_chain_id,
            processing_plan_ids=[plan.processing_plan_id for plan in snapshot.plans],
        )
        return processing


class MetricPlanExecutionService:
    """Execute one locked ProcessingPlan atomically from persisted JSON only."""

    def __init__(
        self,
        db: Session,
        metric_execution_repository: MetricExecutionRepository,
        event_repository: EventRepository,
        processing_plan_repository: ProcessingPlanRepository,
        observation_repository: AnalyticalObservationRepository,
        metrics_extraction_service: MetricsExtractionService,
        *,
        max_attempts: int,
        retry_delay: Callable[[int], float],
    ) -> None:
        self.db = db
        self.metric_execution_repository = metric_execution_repository
        self.event_repository = event_repository
        self.processing_plan_repository = processing_plan_repository
        self.observation_repository = observation_repository
        self.metrics_extraction_service = metrics_extraction_service
        self.max_attempts = max_attempts
        self.retry_delay = retry_delay

    def execute_next(self) -> MetricPlanExecutionResult | None:
        """Lock and execute one eligible order using ``SKIP LOCKED``."""
        execution = self.metric_execution_repository.lock_next_eligible(
            max_attempts=self.max_attempts
        )
        if execution is None:
            return None

        execution.status = MetricPlanExecutionStatus.RUNNING
        execution.attempt_count += 1
        execution.started_at = datetime.now(UTC)
        execution.next_attempt_at = None
        parent = execution.metric_processing_execution
        parent.status = MetricProcessingStatus.PROCESSING
        self.metric_execution_repository.touch_processing(parent)
        observation_count = 0

        try:
            with self.db.begin_nested():
                observation_count = self._execute_locked(execution)
                execution.status = MetricPlanExecutionStatus.SUCCEEDED
                execution.succeeded_at = datetime.now(UTC)
                execution.last_error = None
                execution.is_retryable = False
                self.db.flush()
        except ObservationExtractionError as exc:
            self._record_permanent_failure(execution, exc)
        except Exception as exc:
            self._record_technical_failure(execution, exc)

        self._refresh_parent_status(execution.metric_processing_execution_id)
        return MetricPlanExecutionResult(
            execution_id=execution.id,
            status=str(execution.status),
            observation_count=observation_count,
            error=execution.last_error,
        )

    def _execute_locked(self, execution: MetricPlanExecution) -> int:
        event = self.event_repository.get_by_id(execution.event_id)
        plan = self.processing_plan_repository.find_by_id(execution.processing_plan_id)
        if event is None:
            raise ObservationExtractionError(
                f"MetricPlanExecution {execution.id} references a missing Event"
            )
        if plan is None:
            raise ObservationExtractionError(
                f"MetricPlanExecution {execution.id} references "
                "a missing ProcessingPlan"
            )
        if (
            plan.processing_chain_id != execution.processing_chain_id
            or plan.compiled_plan_json is None
        ):
            raise ObservationExtractionError(
                f"MetricPlanExecution {execution.id} references an incoherent plan"
            )

        inserted = 0
        for observation in self.metrics_extraction_service.extract_for_plan(
            event=event,
            plan=plan,
            execution=execution,
        ):
            if self.observation_repository.add_runtime_observation_if_absent(
                observation
            ):
                inserted += 1
        return inserted

    def _record_permanent_failure(
        self, execution: MetricPlanExecution, error: Exception
    ) -> None:
        execution.status = MetricPlanExecutionStatus.FAILED_PERMANENT
        execution.is_retryable = False
        execution.next_attempt_at = None
        execution.last_error = str(error)[:2000]

    def _record_technical_failure(
        self, execution: MetricPlanExecution, error: Exception
    ) -> None:
        execution.last_error = str(error)[:2000]
        if execution.attempt_count >= self.max_attempts:
            execution.status = MetricPlanExecutionStatus.FAILED_PERMANENT
            execution.is_retryable = False
            execution.next_attempt_at = None
            return
        execution.status = MetricPlanExecutionStatus.RETRYABLE
        execution.is_retryable = True
        execution.next_attempt_at = datetime.now(UTC) + timedelta(
            seconds=self.retry_delay(execution.attempt_count)
        )

    def _refresh_parent_status(self, processing_execution_id: int) -> None:
        plans = self.metric_execution_repository.list_plan_executions(
            processing_execution_id
        )
        parent = plans[0].metric_processing_execution if plans else None
        if parent is None:
            return
        statuses = {plan.status for plan in plans}
        if statuses == {MetricPlanExecutionStatus.SUCCEEDED}:
            parent.status = MetricProcessingStatus.SUCCEEDED
            parent.last_error = None
        elif (
            statuses
            <= {
                MetricPlanExecutionStatus.SUCCEEDED,
                MetricPlanExecutionStatus.FAILED_PERMANENT,
            }
            and MetricPlanExecutionStatus.FAILED_PERMANENT in statuses
        ):
            parent.status = MetricProcessingStatus.COMPLETED_WITH_ERRORS
            parent.last_error = "One or more metric plans failed permanently"
        else:
            parent.status = MetricProcessingStatus.MATERIALIZED
        self.metric_execution_repository.touch_processing(parent)
