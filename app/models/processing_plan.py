from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.metric_definition import MetricDefinition
    from app.models.metric_definition_version import MetricDefinitionVersion
    from app.models.processing_chain import ProcessingChain

JsonDict = dict[str, Any]


class ProcessingPlan(Base):
    __tablename__ = "processing_plan"
    __table_args__ = (
        UniqueConstraint(
            "processing_chain_id",
            "metric_definition_id",
            name="uq_processing_plan_chain_metric_definition",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    processing_chain_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.processing_chain.id"),
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

    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    compiled_plan_json: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    processing_chain: Mapped["ProcessingChain"] = relationship(
        back_populates="plans",
    )

    metric_definition: Mapped["MetricDefinition"] = relationship()
    metric_definition_version: Mapped["MetricDefinitionVersion"] = relationship()