from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from app.database import Base
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.event_type import EventType
    from app.models.metric_definition import MetricDefinition
    from app.models.metric_definition_version import MetricDefinitionVersion
    from app.models.project import Project


class MetricState(Base):
    """
    Current Prometheus-ready state of one business metric time series.

    MetricState stores the already aggregated value exposed by the /metrics
    endpoint. It is intentionally not an event log: raw events and analytical
    observations remain the durable history, while this table materializes the
    current counter value for one metric and one exact label set.
    """

    __tablename__ = "metric_state"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "event_type_id",
            "metric_code",
            "labels_hash",
            name="uq_metric_state_series",
        ),
        Index(
            "ix_metric_state_project_event_type_metric",
            "project_id",
            "event_type_id",
            "metric_code",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.project.id"),
        nullable=False,
        index=True,
    )

    event_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.event_type.id"),
        nullable=False,
        index=True,
    )

    metric_definition_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("outbox.metric_definition.id"),
        nullable=True,
        index=True,
    )

    metric_definition_version_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("outbox.metric_definition_version.id"),
        nullable=True,
        index=True,
    )

    metric_code: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    labels_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    labels_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["Project"] = relationship()
    event_type: Mapped["EventType"] = relationship()
    metric_definition: Mapped[Optional["MetricDefinition"]] = relationship()
    metric_definition_version: Mapped[Optional["MetricDefinitionVersion"]] = relationship()
