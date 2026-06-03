from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.event_type import EventType
    from app.models.processing_plan import ProcessingPlan
    from app.models.schema_definition import SchemaDefinition


class ProcessingChain(Base):
    __tablename__ = "processing_chain"
    __table_args__ = (
        UniqueConstraint(
            "event_type_id",
            "schema_definition_id",
            "version_number",
            name="uq_processing_chain_scope_version",
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

    schema_definition_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.schema_definition.id"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event_type: Mapped["EventType"] = relationship()
    schema_definition: Mapped["SchemaDefinition"] = relationship()

    plans: Mapped[list["ProcessingPlan"]] = relationship(
        back_populates="processing_chain",
        cascade="all, delete-orphan",
    )