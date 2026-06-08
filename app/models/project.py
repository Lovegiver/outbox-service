from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.database import Base
from sqlalchemy import Boolean, String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.metrics_token import MetricsToken
    from app.models.project_member import ProjectMember
    from app.models.event import Event
    from app.models.event_type import EventType


class Project(Base):
    __tablename__ = "project"
    __table_args__ = {"schema": "outbox"}

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
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

    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    metrics_tokens: Mapped[list["MetricsToken"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )