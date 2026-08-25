from contextlib import contextmanager
from types import SimpleNamespace

from app.core.metric_execution_status import (
    MetricPlanExecutionStatus,
    MetricProcessingStatus,
)
from app.metrics_engine.compiled_processing_plan import (
    CompiledProcessingPlan,
    CompiledProcessingSnapshot,
)
from app.metrics_engine.observation_extractor import ObservationExtractionError
from app.services.metric_runtime_service import (
    MetricExecutionMaterializationService,
    MetricPlanExecutionService,
)


class FakeDb:
    def __init__(self) -> None:
        self.flush_count = 0

    @contextmanager
    def begin_nested(self):
        yield

    def flush(self) -> None:
        self.flush_count += 1


class FakeExecutionRepository:
    def __init__(self, execution=None) -> None:
        self.execution = execution
        self.touched = []
        self.processing_by_event = None
        self.created_processing = None
        self.created_plan_ids = []
        self.failed_plan = None

    def lock_next_eligible(self, *, max_attempts: int):
        return self.execution

    def list_plan_executions(self, _processing_execution_id: int):
        return [self.execution] if self.execution is not None else []

    def touch_processing(self, processing):
        self.touched.append(processing.status)
        return processing

    def find_processing_by_event_id(self, _event_id: int):
        return self.processing_by_event

    def create_processing_if_absent(self, **kwargs):
        self.created_processing = SimpleNamespace(id=41, **kwargs)
        return self.created_processing

    def create_plan_executions_if_absent(self, **kwargs):
        self.created_plan_ids = kwargs["processing_plan_ids"]

    def create_failed_plan_execution_if_absent(self, **kwargs):
        self.failed_plan = kwargs


class FakeProvider:
    def __init__(self, snapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    def get_active_snapshot(self, **_kwargs):
        self.calls += 1
        return self.snapshot


def _execution() -> SimpleNamespace:
    parent = SimpleNamespace(id=5, status=MetricProcessingStatus.MATERIALIZED)
    return SimpleNamespace(
        id=7,
        status=MetricPlanExecutionStatus.PENDING,
        attempt_count=0,
        started_at=None,
        next_attempt_at=None,
        succeeded_at=None,
        last_error=None,
        is_retryable=True,
        event_id=1,
        processing_chain_id=2,
        processing_plan_id=3,
        metric_processing_execution_id=5,
        metric_processing_execution=parent,
    )


def _execution_service(*, extraction_result=None, extraction_error=None, attempts=3):
    execution = _execution()
    repository = FakeExecutionRepository(execution)
    event = SimpleNamespace(id=1)
    plan = SimpleNamespace(id=3, processing_chain_id=2, compiled_plan_json={})

    class ExtractionService:
        def extract_for_plan(self, **_kwargs):
            if extraction_error is not None:
                raise extraction_error
            return extraction_result or []

    class ObservationRepository:
        def add_runtime_observation_if_absent(self, _observation):
            return True

    service = MetricPlanExecutionService(
        db=FakeDb(),
        metric_execution_repository=repository,
        event_repository=SimpleNamespace(get_by_id=lambda _id: event),
        processing_plan_repository=SimpleNamespace(find_by_id=lambda _id: plan),
        observation_repository=ObservationRepository(),
        metrics_extraction_service=ExtractionService(),
        max_attempts=attempts,
        retry_delay=lambda _attempt: 4,
    )
    return service, repository, execution


def test_materialization_reuses_frozen_snapshot_without_provider_lookup() -> None:
    existing = SimpleNamespace(id=9, processing_chain_id=8)
    repository = FakeExecutionRepository()
    repository.processing_by_event = existing
    provider = FakeProvider(snapshot=None)
    service = MetricExecutionMaterializationService(provider, repository)

    result = service.materialize_for_event(SimpleNamespace(id=1))

    assert result is existing
    assert provider.calls == 0


def test_materialization_creates_all_plan_orders_for_exact_snapshot() -> None:
    snapshot = CompiledProcessingSnapshot(
        processing_chain_id=8,
        plans=(
            CompiledProcessingPlan(8, 10, 20, 30, 0, {}),
            CompiledProcessingPlan(8, 11, 21, 31, 1, {}),
        ),
    )
    repository = FakeExecutionRepository()
    service = MetricExecutionMaterializationService(FakeProvider(snapshot), repository)
    event = SimpleNamespace(
        id=1,
        project_id=2,
        event_type_id=3,
        schema_definition_id=4,
        json_version_internal="1",
        event_type=SimpleNamespace(project_id=2),
        schema_definition=SimpleNamespace(
            event_type_id=3,
            json_version_internal="1",
        ),
    )

    result = service.materialize_for_event(event)

    assert result.status == MetricProcessingStatus.MATERIALIZED
    assert repository.created_plan_ids == [10, 11]


def test_success_atomically_marks_plan_and_parent_succeeded() -> None:
    service, repository, execution = _execution_service(
        extraction_result=[object(), object()]
    )

    result = service.execute_next()

    assert result.status == MetricPlanExecutionStatus.SUCCEEDED
    assert result.observation_count == 2
    assert execution.attempt_count == 1
    assert (
        execution.metric_processing_execution.status == MetricProcessingStatus.SUCCEEDED
    )
    assert repository.touched[0] == MetricProcessingStatus.PROCESSING


def test_structural_plan_failure_is_permanent_and_visible() -> None:
    service, _, execution = _execution_service(
        extraction_error=ObservationExtractionError("unknown operation")
    )

    result = service.execute_next()

    assert result.status == MetricPlanExecutionStatus.FAILED_PERMANENT
    assert result.error == "unknown operation"
    assert execution.is_retryable is False
    assert (
        execution.metric_processing_execution.status
        == MetricProcessingStatus.COMPLETED_WITH_ERRORS
    )


def test_technical_failure_is_retryable_until_attempt_limit() -> None:
    service, _, execution = _execution_service(
        extraction_error=RuntimeError("temporary database failure")
    )

    first = service.execute_next()

    assert first.status == MetricPlanExecutionStatus.RETRYABLE
    assert execution.is_retryable is True
    assert execution.next_attempt_at is not None

    execution.status = MetricPlanExecutionStatus.RETRYABLE
    execution.next_attempt_at = None
    execution.attempt_count = 2
    final = service.execute_next()

    assert final.status == MetricPlanExecutionStatus.FAILED_PERMANENT
    assert execution.attempt_count == 3
    assert execution.is_retryable is False
