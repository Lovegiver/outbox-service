from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.project import Project
    from app.models.route_definition import RouteDefinition
    from app.models.schema_definition import SchemaDefinition


class EventType(Base):
    __tablename__ = "event_type"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "code",
            name="uq_event_type_project_code",
        ),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("outbox.project.id"),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    project: Mapped[Project] = relationship(
        back_populates="event_types",
    )

    schemas: Mapped[list[SchemaDefinition]] = relationship(
        back_populates="event_type",
        cascade="all, delete-orphan",
    )

    routes: Mapped[list[RouteDefinition]] = relationship(
        back_populates="event_type",
        cascade="all, delete-orphan",
    )

    events: Mapped[list[Event]] = relationship(
        back_populates="event_type",
        cascade="all, delete-orphan",
    )