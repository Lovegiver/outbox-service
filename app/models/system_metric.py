from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemMetric(Base):
    __tablename__ = "system_metric"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    metric_code: Mapped[str] = mapped_column(
        String(100)
    )

    project_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("outbox.project.id"),
        nullable=True
    )

    event_type_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True
    )

    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )

    value: Mapped[float] = mapped_column(
        Numeric
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

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