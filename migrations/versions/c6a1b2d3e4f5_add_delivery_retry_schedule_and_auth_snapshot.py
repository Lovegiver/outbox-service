"""add delivery retry schedule and authentication snapshot

Revision ID: c6a1b2d3e4f5
Revises: 8cd8381d1f4d
Create Date: 2026-08-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6a1b2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "8cd8381d1f4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event_delivery",
        sa.Column(
            "auth_type",
            sa.String(length=30),
            server_default="NONE",
            nullable=False,
        ),
        schema="outbox",
    )
    op.add_column(
        "event_delivery",
        sa.Column("auth_config", sa.JSON(), nullable=True),
        schema="outbox",
    )
    op.add_column(
        "event_delivery",
        sa.Column("secret_ref", sa.String(length=255), nullable=True),
        schema="outbox",
    )
    op.add_column(
        "event_delivery",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        schema="outbox",
    )
    op.create_index(
        "ix_event_delivery_retry_schedule",
        "event_delivery",
        ["status", "next_attempt_at"],
        unique=False,
        schema="outbox",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_event_delivery_retry_schedule",
        table_name="event_delivery",
        schema="outbox",
    )
    op.drop_column("event_delivery", "next_attempt_at", schema="outbox")
    op.drop_column("event_delivery", "secret_ref", schema="outbox")
    op.drop_column("event_delivery", "auth_config", schema="outbox")
    op.drop_column("event_delivery", "auth_type", schema="outbox")
