from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.metric_plan_execution import MetricPlanExecution
    from app.models.processing_chain import ProcessingChain


class MetricProcessingExecution(Base):
    """Frozen metric snapshot selected for one Event at first processing."""

    __tablename__ = "metric_processing_execution"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_metric_processing_execution_event"),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("outbox.event.id"), nullable=False, index=True
    )
    processing_chain_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("outbox.processing_chain.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    event: Mapped["Event"] = relationship()
    processing_chain: Mapped["ProcessingChain"] = relationship()
    plan_executions: Mapped[list["MetricPlanExecution"]] = relationship(
        back_populates="metric_processing_execution",
        cascade="all, delete-orphan",
    )
