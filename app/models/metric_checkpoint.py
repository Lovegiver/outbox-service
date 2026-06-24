from __future__ import annotations

from datetime import datetime

from app.database import Base
from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column


class MetricCheckpoint(Base):
    """
    Durable aggregation cursor for Prometheus metric state computation.

    The checkpoint records the last AnalyticalObservation id incorporated into
    MetricState for one logical worker stream. Updating this checkpoint in the
    same transaction as MetricState prevents data loss and double counting.
    """

    __tablename__ = "metric_checkpoint"
    __table_args__ = (
        UniqueConstraint(
            "checkpoint_name",
            name="uq_metric_checkpoint_name",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    checkpoint_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    last_processed_observation_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
