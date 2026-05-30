from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.event_type import EventType
    from app.models.project import Project


class MetricsToken(Base):
    __tablename__ = "metrics_token"
    __table_args__ = {"schema": "outbox"}

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    project_id: Mapped[int] = mapped_column(
        ForeignKey("outbox.project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("outbox.event_type.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    token_prefix: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="metrics_tokens")
    event_type: Mapped["EventType | None"] = relationship(back_populates="metrics_tokens")