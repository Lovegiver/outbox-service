from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from typing import Any, Optional

from sqlalchemy import distinct, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.analytical_observation import AnalyticalObservation
from app.models.event_type import EventType
from app.models.metric_checkpoint import MetricCheckpoint
from app.models.metric_state import MetricState


@dataclass(frozen=True)
class MetricObservationStream:
    """
    Identifies one independent Prometheus aggregation stream.

    Args:
        project_id: Project owning the analytical observations.
        event_type_id: EventType whose observations must be materialized.
    """

    project_id: int
    event_type_id: int


@dataclass(frozen=True)
class MetricStateDelta:
    """
    Aggregation delta for one Prometheus time series.

    Args:
        project_id: Project owning the metric series.
        event_type_id: EventType that produced the metric series.
        metric_definition_id: Optional MetricDefinition source id.
        metric_definition_version_id: Optional MetricDefinitionVersion source id.
        metric_code: Prometheus-compatible logical metric code.
        labels_json: Label set identifying the Prometheus series.
        labels_hash: Stable hash generated from labels_json.
        value: Numeric delta to add to the current counter state.
    """

    project_id: int
    event_type_id: int
    metric_definition_id: Optional[int]
    metric_definition_version_id: Optional[int]
    metric_code: str
    labels_json: dict[str, Any]
    labels_hash: str
    value: float


@dataclass(frozen=True)
class PrometheusMetricStateRow:
    """Joined, read-only representation used by Prometheus exposition."""

    state_id: int
    project_id: int
    event_type_id: int
    event_type_project_id: int
    event_type_code: str
    metric_code: str
    labels_json: object
    value: float


class MetricStateRepository:
    """
    Repository for Prometheus-ready metric state and aggregation checkpoints.

    The repository only performs persistence operations. Transaction boundaries
    remain owned by the worker/runtime that orchestrates aggregation.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_observation_streams(self) -> list[MetricObservationStream]:
        """
        Return project/EventType streams that currently have observations.

        Returns:
            Distinct streams found in the analytical observation log.
        """

        statement = (
            select(
                distinct(AnalyticalObservation.project_id),
                AnalyticalObservation.event_type_id,
            )
            .order_by(
                AnalyticalObservation.project_id.asc(),
                AnalyticalObservation.event_type_id.asc(),
            )
        )

        return [
            MetricObservationStream(
                project_id=int(row[0]),
                event_type_id=int(row[1]),
            )
            for row in self.db.execute(statement).all()
        ]

    def find_observations_after(
        self,
        project_id: int,
        event_type_id: int,
        observation_id: int,
        limit: int = 1000,
    ) -> list[AnalyticalObservation]:
        """
        Load stream observations not yet aggregated into MetricState.

        Args:
            project_id: Project owning the observations.
            event_type_id: EventType whose observations must be loaded.
            observation_id: Last processed observation id for this stream.
            limit: Maximum number of observations to load.

        Returns:
            Ordered observations with id greater than observation_id for the
            requested project/EventType stream.
        """

        statement = (
            select(AnalyticalObservation)
            .where(
                AnalyticalObservation.project_id == project_id,
                AnalyticalObservation.event_type_id == event_type_id,
                AnalyticalObservation.id > observation_id,
            )
            .order_by(AnalyticalObservation.id.asc())
            .limit(limit)
        )

        return list(self.db.execute(statement).scalars().all())

    def get_or_create_checkpoint(
        self,
        checkpoint_name: str,
    ) -> MetricCheckpoint:
        """
        Return an existing checkpoint or create an initial one at position 0.

        Args:
            checkpoint_name: Logical checkpoint stream name.

        Returns:
            Locked persistent MetricCheckpoint instance.
        """

        create_statement = (
            insert(MetricCheckpoint)
            .values(
                checkpoint_name=checkpoint_name,
                last_processed_observation_id=0,
            )
            .on_conflict_do_nothing(
                constraint="uq_metric_checkpoint_name",
            )
        )
        self.db.execute(create_statement)

        lock_statement = (
            select(MetricCheckpoint)
            .where(MetricCheckpoint.checkpoint_name == checkpoint_name)
            .with_for_update()
        )
        return self.db.execute(lock_statement).scalar_one()

    def upsert_delta(self, delta: MetricStateDelta) -> None:
        """
        Add a delta to the current value of one Prometheus metric series.

        Args:
            delta: Aggregated value to merge into MetricState.
        """

        now = datetime.now(UTC)

        statement = (
            insert(MetricState)
            .values(
                project_id=delta.project_id,
                event_type_id=delta.event_type_id,
                metric_definition_id=delta.metric_definition_id,
                metric_definition_version_id=delta.metric_definition_version_id,
                metric_code=delta.metric_code,
                labels_hash=delta.labels_hash,
                labels_json=delta.labels_json,
                value=delta.value,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_metric_state_series",
                set_={
                    "value": MetricState.value + delta.value,
                    "labels_json": delta.labels_json,
                    "metric_definition_id": delta.metric_definition_id,
                    "metric_definition_version_id": (
                        delta.metric_definition_version_id
                    ),
                    "updated_at": now,
                },
            )
        )

        self.db.execute(statement)

    def update_checkpoint(
        self,
        checkpoint: MetricCheckpoint,
        last_processed_observation_id: int,
    ) -> MetricCheckpoint:
        """
        Move the checkpoint to the latest durably aggregated observation.

        Args:
            checkpoint: Locked checkpoint row.
            last_processed_observation_id: Last observation id included in state.

        Returns:
            Updated checkpoint instance.
        """

        checkpoint.last_processed_observation_id = last_processed_observation_id
        checkpoint.updated_at = datetime.now(UTC)
        self.db.add(checkpoint)
        self.db.flush()

        return checkpoint

    def find_states_by_event_type(
        self,
        event_type_id: int,
    ) -> list[MetricState]:
        """
        Return Prometheus-ready states for one EventType.

        Args:
            event_type_id: EventType identifier exposed by the scrape endpoint.

        Returns:
            Materialized metric states belonging to the EventType.
        """

        statement = (
            select(MetricState)
            .where(MetricState.event_type_id == event_type_id)
            .order_by(
                MetricState.project_id.asc(),
                MetricState.metric_code.asc(),
                MetricState.labels_hash.asc(),
            )
        )

        return list(self.db.execute(statement).scalars().all())

    def find_prometheus_rows_by_project(
        self,
        project_id: int,
    ) -> list[PrometheusMetricStateRow]:
        """
        Load all materialized series and platform label data for one Project.

        EventType codes are joined in one query so rendering never triggers
        lazy relationship loading or N+1 queries. Project existence and its
        stable name are loaded once by the application service.
        """

        statement = (
            select(
                MetricState.id,
                MetricState.project_id,
                MetricState.event_type_id,
                EventType.project_id,
                EventType.code,
                MetricState.metric_code,
                MetricState.labels_json,
                MetricState.value,
            )
            .join(EventType, EventType.id == MetricState.event_type_id)
            .where(MetricState.project_id == project_id)
            .order_by(
                MetricState.metric_code.asc(),
                EventType.code.asc(),
                MetricState.labels_hash.asc(),
                MetricState.id.asc(),
            )
        )

        return [
            PrometheusMetricStateRow(
                state_id=int(row[0]),
                project_id=int(row[1]),
                event_type_id=int(row[2]),
                event_type_project_id=int(row[3]),
                event_type_code=str(row[4]),
                metric_code=str(row[5]),
                labels_json=row[6],
                value=float(row[7]),
            )
            for row in self.db.execute(statement).all()
        ]

    def find_all_states(self) -> list[MetricState]:
        """
        Return all Prometheus-ready metric states ordered by metric name.

        Returns:
            Materialized metric states.
        """

        statement = (
            select(MetricState)
            .order_by(
                MetricState.project_id.asc(),
                MetricState.event_type_id.asc(),
                MetricState.metric_code.asc(),
                MetricState.labels_hash.asc(),
            )
        )

        return list(self.db.execute(statement).scalars().all())


def build_checkpoint_name(project_id: int, event_type_id: int) -> str:
    """
    Build the durable checkpoint name for one project/EventType stream.

    Args:
        project_id: Project owning the observation stream.
        event_type_id: EventType owning the observation stream.

    Returns:
        Stable checkpoint name encoded in the schema already migrated.
    """

    return f"prometheus_metric_state:{project_id}:{event_type_id}"


def build_labels_hash(labels: dict[str, Any]) -> str:
    """
    Build a stable SHA-256 hash for a Prometheus label set.

    Args:
        labels: JSON-compatible labels dictionary.

    Returns:
        Hexadecimal SHA-256 hash of the normalized labels.
    """

    normalized = json.dumps(
        labels,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
