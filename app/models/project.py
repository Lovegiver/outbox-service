from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.event_type import EventType


class Project(Base):
    __tablename__ = "project"
    __table_args__ = {"schema": "outbox"}

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
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

    event_types: Mapped[list[EventType]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    events: Mapped[list[Event]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )