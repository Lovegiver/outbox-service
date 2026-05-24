from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy import DateTime, String, BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Event(Base):
    __tablename__ = "event"
    __table_args__ = {"schema": "outbox"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    event_uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        unique=True
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.project.id"),
        nullable=False
    )

    event_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.event_type.id"),
        nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(30), nullable=False, default="1.0")

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="RECEIVED")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )