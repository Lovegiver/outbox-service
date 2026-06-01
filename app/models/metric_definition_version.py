from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.metric_definition import MetricDefinition
    from app.models.metric_definition_version_schema import MetricDefinitionVersionSchema


class MetricDefinitionVersion(Base):
    __tablename__ = "metric_definition_version"
    __table_args__ = (
        UniqueConstraint(
            "metric_definition_id",
            "yaml_version_number",
            name="uq_metric_definition_yaml_version_number",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    metric_definition_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.metric_definition.id"),
        nullable=False,
        index=True,
    )

    yaml_version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    yaml_version_label: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    yaml_content: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    metric_definition: Mapped["MetricDefinition"] = relationship(
        back_populates="versions",
    )

    schema_compatibilities: Mapped[list["MetricDefinitionVersionSchema"]] = relationship(
        back_populates="metric_definition_version",
        cascade="all, delete-orphan",
    )