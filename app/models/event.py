from datetime import datetime, timezone
from uuid import uuid4

from app.database import Base
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class Event(Base):
    __tablename__ = "event"
    __table_args__ = {"schema": "outbox"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid4)

    project: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(150), nullable=False)
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