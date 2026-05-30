from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.auth_type import AuthType
from app.database import Base
from sqlalchemy import BigInteger, Boolean, ForeignKey, String, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.event_type import EventType


class RouteDefinition(Base):
    __tablename__ = "route_definition"
    __table_args__ = (
        UniqueConstraint(
            "event_type_id",
            "routing_key",
            "destination_url",
            name="uq_route_event_type_routing_destination",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    event_type_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.event_type.id"),
        nullable=False,
    )

    routing_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    destination_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    destination_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    auth_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=AuthType.NONE,
    )

    auth_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    secret_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    event_type: Mapped[EventType] = relationship(
        back_populates="routes",
    )