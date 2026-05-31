from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.metric_definition_version import MetricDefinitionVersion
    from app.models.schema_definition import SchemaDefinition


class MetricDefinitionVersionSchema(Base):
    __tablename__ = "metric_definition_version_schema"
    __table_args__ = (
        UniqueConstraint(
            "metric_definition_version_id",
            "schema_definition_id",
            name="uq_metric_definition_version_schema",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    metric_definition_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.metric_definition_version.id"),
        nullable=False,
        index=True,
    )

    schema_definition_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.schema_definition.id"),
        nullable=False,
        index=True,
    )

    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    metric_definition_version: Mapped["MetricDefinitionVersion"] = relationship(
        back_populates="schema_compatibilities",
    )

    schema_definition: Mapped["SchemaDefinition"] = relationship()