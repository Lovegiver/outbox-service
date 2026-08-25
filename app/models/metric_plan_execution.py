from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.metric_processing_execution import MetricProcessingExecution
    from app.models.processing_chain import ProcessingChain
    from app.models.processing_plan import ProcessingPlan


class MetricPlanExecution(Base):
    """Durable, retryable execution of one ProcessingPlan for one Event."""

    __tablename__ = "metric_plan_execution"
    __table_args__ = (
        UniqueConstraint(
            "event_id", "processing_plan_id", name="uq_metric_plan_execution_event_plan"
        ),
        Index(
            "ix_metric_plan_execution_retry_schedule",
            "status",
            "next_attempt_at",
            "created_at",
            "id",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    metric_processing_execution_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.metric_processing_execution.id"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("outbox.event.id"), nullable=False, index=True
    )
    processing_chain_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("outbox.processing_chain.id"), nullable=False, index=True
    )
    processing_plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("outbox.processing_plan.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    succeeded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    metric_processing_execution: Mapped["MetricProcessingExecution"] = relationship(
        back_populates="plan_executions"
    )
    event: Mapped["Event"] = relationship()
    processing_chain: Mapped["ProcessingChain"] = relationship()
    processing_plan: Mapped["ProcessingPlan"] = relationship()
