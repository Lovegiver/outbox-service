from datetime import datetime
from typing import TYPE_CHECKING

from app.core.auth_enums import ProjectMemberRole
from app.database import Base
from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.user_account import UserAccount


class ProjectMember(Base):
    __tablename__ = "project_member"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
        {"schema": "outbox"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    project_id: Mapped[int] = mapped_column(
        ForeignKey("outbox.project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("outbox.user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[ProjectMemberRole] = mapped_column(
        Enum(ProjectMemberRole, name="project_member_role", schema="outbox"),
        nullable=False,
        default=ProjectMemberRole.VIEWER,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship(back_populates="members")
    user: Mapped["UserAccount"] = relationship(back_populates="project_memberships")