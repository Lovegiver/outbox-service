from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.event_type import EventType


class SystemMetric(Base):
    __tablename__ = "system_metric"

    __table_args__ = (
        UniqueConstraint(
            "metric_code",
            "project_id",
            "event_type_id",
            "period_start",
            "period_end",
            name="uq_system_metric_period",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    metric_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    project_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("outbox.project.id"),
        nullable=True,
    )

    event_type_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("outbox.event_type.id"),
        nullable=True,
    )

    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    value: Mapped[float] = mapped_column(
        Numeric,
        nullable=False,
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project | None] = relationship()

    event_type: Mapped[EventType | None] = relationship()