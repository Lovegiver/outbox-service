from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from app.database import Base
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.event_type import EventType
    from app.models.metric_definition import MetricDefinition
    from app.models.metric_definition_version import MetricDefinitionVersion
    from app.models.project import Project


class AnalyticalObservation(Base):
    __tablename__ = "analytical_observation"
    __table_args__ = (
        Index(
            "ix_analytical_observation_project_event_type_metric_observed_at",
            "project_id",
            "event_type_id",
            "metric_code",
            "observed_at",
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

    event_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.event.id"),
        nullable=False,
        index=True,
    )

    metric_definition_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.metric_definition.id"),
        nullable=False,
        index=True,
    )

    metric_definition_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.metric_definition_version.id"),
        nullable=False,
        index=True,
    )

    metric_code: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    value: Mapped[float] = mapped_column(Float, nullable=False)

    dimensions_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    project: Mapped["Project"] = relationship()
    event_type: Mapped["EventType"] = relationship()
    event: Mapped["Event"] = relationship()
    metric_definition: Mapped["MetricDefinition"] = relationship()
    metric_definition_version: Mapped["MetricDefinitionVersion"] = relationship()