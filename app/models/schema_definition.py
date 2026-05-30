from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.event_type import EventType


class SchemaDefinition(Base):
    __tablename__ = "schema_definition"
    __table_args__ = (
        UniqueConstraint(
            "event_type_id",
            "json_version_internal",
            name="uq_schema_event_type_internal_version",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    event_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.event_type.id"),
        nullable=False,
    )

    json_version_client: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    json_version_internal: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="1.0",
    )

    json_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    event_type: Mapped[EventType] = relationship(back_populates="schemas")