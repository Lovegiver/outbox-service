from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RouteDefinition(Base):
    __tablename__ = "route_definition"
    __table_args__ = {"schema": "outbox"}

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

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )