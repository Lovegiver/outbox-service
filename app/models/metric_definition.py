from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.event_type import EventType
    from app.models.metric_definition_version import MetricDefinitionVersion


class MetricDefinition(Base):
    __tablename__ = "metric_definition"
    __table_args__ = (
        UniqueConstraint(
            "event_type_id",
            "code",
            name="uq_metric_definition_event_type_code",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    event_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.event_type.id"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(String(150), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    event_type: Mapped["EventType"] = relationship(
        back_populates="metric_definitions",
    )

    versions: Mapped[list["MetricDefinitionVersion"]] = relationship(
        back_populates="metric_definition",
        cascade="all, delete-orphan",
    )