from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from app.database import Base
from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.event_type import EventType
    from app.models.project import Project
    from app.models.event_delivery import EventDelivery
    from app.models.schema_definition import SchemaDefinition


class Event(Base):
    """
    Persistent Outbox event accepted by the ingress layer.

    An Event represents a validated business payload durably stored by OB1.
    The event_uuid uniquely identifies this specific event occurrence, while
    correlation_id can link several events that belong to the same distributed
    business process or runtime flow.
    """

    __tablename__ = "event"
    __table_args__ = {"schema": "outbox"}

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    event_uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        unique=True,
    )

    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    """
    Optional identifier used to correlate multiple events belonging
    to the same distributed business process or runtime flow.
    """

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.project.id"),
        nullable=False,
    )

    event_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.event_type.id"),
        nullable=False,
    )

    json_version_internal: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="1.0",
        server_default="1.0",
    )

    schema_definition_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.schema_definition.id"),
        nullable=False,
    )

    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="RECEIVED",
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

    project: Mapped[Project] = relationship(
        back_populates="events",
    )

    event_type: Mapped[EventType] = relationship(
        back_populates="events",
    )

    deliveries: Mapped[list[EventDelivery]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )

    schema_definition: Mapped["SchemaDefinition"] = relationship(
        back_populates="events",
    )