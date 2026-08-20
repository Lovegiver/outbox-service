from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import func, select, text

from app.database import SessionLocal, engine
from app.models.metric_checkpoint import MetricCheckpoint
from app.models.metric_state import MetricState
from app.repositories.metric_state_repository import (
    MetricStateRepository,
    build_checkpoint_name,
)
from app.services.metric_state_aggregation_service import (
    MetricStateAggregationService,
)
from tests.domain.record import (
    AnalyticalObservationRecord,
    EventRecord,
    EventTypeRecord,
    MetricDefinitionRecord,
    MetricDefinitionVersionRecord,
    ProjectRecord,
    SchemaDefinitionRecord,
)
from tests.infrastructure.object_factory import ObjectFactory


def test_concurrent_checkpoint_initialization_is_idempotent() -> None:
    suffix = uuid4().hex

    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        project = factory.project(ProjectRecord(name=f"checkpoint-{suffix}"))
        event_type = factory.event_type(
            EventTypeRecord(
                project=project,
                code=f"counter.{suffix}",
                name="Concurrent counter",
            )
        )
        schema = factory.schema_definition(
            SchemaDefinitionRecord(event_type=event_type)
        )
        event = factory.event(
            EventRecord(
                event_type=event_type,
                schema_definition=schema,
            )
        )
        metric_definition = factory.metric_definition(
            MetricDefinitionRecord(
                event_type=event_type,
                code="concurrent_total",
                name="Concurrent total",
            )
        )
        metric_version = factory.metric_definition_version(
            MetricDefinitionVersionRecord(
                metric_definition=metric_definition,
            )
        )
        observation = factory.analytical_observation(
            AnalyticalObservationRecord(
                event=event,
                metric_definition=metric_definition,
                metric_definition_version=metric_version,
                metric_code="concurrent_total",
                value=5,
                dimensions_json={"country": "FR"},
            )
        )

    checkpoint_name = build_checkpoint_name(project.id, event_type.id)
    barrier = Barrier(2)

    def aggregate_concurrently() -> int:
        with SessionLocal() as session:
            service = MetricStateAggregationService(
                MetricStateRepository(session)
            )
            barrier.wait(timeout=10)
            consumed = service.aggregate_stream(
                project_id=project.id,
                event_type_id=event_type.id,
            )
            session.commit()
            return consumed

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(aggregate_concurrently)
                for _ in range(2)
            ]
            consumed_counts = [future.result(timeout=20) for future in futures]

        assert sorted(consumed_counts) == [0, 1]

        with SessionLocal() as session:
            checkpoint_count = session.scalar(
                select(func.count(MetricCheckpoint.id)).where(
                    MetricCheckpoint.checkpoint_name == checkpoint_name
                )
            )
            checkpoint = session.scalar(
                select(MetricCheckpoint).where(
                    MetricCheckpoint.checkpoint_name == checkpoint_name
                )
            )
            states = list(
                session.scalars(
                    select(MetricState).where(
                        MetricState.project_id == project.id,
                        MetricState.event_type_id == event_type.id,
                    )
                )
            )
            third_consumed_count = MetricStateAggregationService(
                MetricStateRepository(session)
            ).aggregate_stream(
                project_id=project.id,
                event_type_id=event_type.id,
            )
            checkpoint_position = (
                checkpoint.last_processed_observation_id
                if checkpoint is not None
                else None
            )
            state_values = [state.value for state in states]
            session.commit()

        assert checkpoint_count == 1
        assert checkpoint_position == observation.id
        assert state_values == [5]
        assert third_consumed_count == 0

    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM outbox.metric_checkpoint "
                    "WHERE checkpoint_name = :checkpoint_name"
                ),
                {"checkpoint_name": checkpoint_name},
            )
            connection.execute(
                text(
                    "DELETE FROM outbox.metric_state "
                    "WHERE project_id = :project_id"
                ),
                {"project_id": project.id},
            )
            connection.execute(
                text(
                    "DELETE FROM outbox.analytical_observation "
                    "WHERE project_id = :project_id"
                ),
                {"project_id": project.id},
            )
            connection.execute(
                text("DELETE FROM outbox.event WHERE project_id = :project_id"),
                {"project_id": project.id},
            )
            connection.execute(
                text(
                    "DELETE FROM outbox.metric_definition_version "
                    "WHERE metric_definition_id = :metric_definition_id"
                ),
                {"metric_definition_id": metric_definition.id},
            )
            connection.execute(
                text(
                    "DELETE FROM outbox.metric_definition "
                    "WHERE event_type_id = :event_type_id"
                ),
                {"event_type_id": event_type.id},
            )
            connection.execute(
                text(
                    "DELETE FROM outbox.schema_definition "
                    "WHERE event_type_id = :event_type_id"
                ),
                {"event_type_id": event_type.id},
            )
            connection.execute(
                text("DELETE FROM outbox.event_type WHERE id = :event_type_id"),
                {"event_type_id": event_type.id},
            )
            connection.execute(
                text("DELETE FROM outbox.project WHERE id = :project_id"),
                {"project_id": project.id},
            )
