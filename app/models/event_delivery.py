from datetime import datetime, timezone

from app.core.delivery_status import DeliveryStatus
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core import delivery_status
from app.database import Base


class EventDelivery(Base):
    __tablename__ = "event_delivery"
    __table_args__ = {"schema": "outbox"}

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    event_id: Mapped[int] = mapped_column(
        ForeignKey("outbox.event.id"),
        nullable=False,
    )

    destination_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    destination_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    destination_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=DeliveryStatus.PENDING,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    last_error: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )