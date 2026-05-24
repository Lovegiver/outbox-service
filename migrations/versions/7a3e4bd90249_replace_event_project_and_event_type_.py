"""replace event project and event type with foreign keys

Revision ID: 7a3e4bd90249
Revises: 1165a7627178
Create Date: 2026-05-24 16:45:19.078552

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7a3e4bd90249"
down_revision: Union[str, Sequence[str], None] = "1165a7627178"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_type",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=150), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["outbox.project.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "code",
            name="uq_event_type_project_code",
        ),
        schema="outbox",
    )

    op.add_column(
        "event",
        sa.Column("event_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        schema="outbox",
    )

    op.add_column(
        "event",
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        schema="outbox",
    )

    op.add_column(
        "event",
        sa.Column("event_type_id", sa.BigInteger(), nullable=False),
        schema="outbox",
    )

    op.create_unique_constraint(
        "uq_event_event_uuid",
        "event",
        ["event_uuid"],
        schema="outbox",
    )

    op.create_foreign_key(
        "fk_event_project_id",
        "event",
        "project",
        ["project_id"],
        ["id"],
        source_schema="outbox",
        referent_schema="outbox",
    )

    op.create_foreign_key(
        "fk_event_event_type_id",
        "event",
        "event_type",
        ["event_type_id"],
        ["id"],
        source_schema="outbox",
        referent_schema="outbox",
    )

    op.drop_constraint(
        "event_event_id_key",
        "event",
        schema="outbox",
        type_="unique",
    )

    op.drop_column("event", "event_id", schema="outbox")
    op.drop_column("event", "project", schema="outbox")
    op.drop_column("event", "event_type", schema="outbox")


def downgrade() -> None:
    op.add_column(
        "event",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        schema="outbox",
    )

    op.add_column(
        "event",
        sa.Column("project", sa.String(length=100), nullable=False),
        schema="outbox",
    )

    op.add_column(
        "event",
        sa.Column("event_type", sa.String(length=150), nullable=False),
        schema="outbox",
    )

    op.create_unique_constraint(
        "event_event_id_key",
        "event",
        ["event_id"],
        schema="outbox",
    )

    op.drop_constraint(
        "fk_event_event_type_id",
        "event",
        schema="outbox",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_event_project_id",
        "event",
        schema="outbox",
        type_="foreignkey",
    )

    op.drop_constraint(
        "uq_event_event_uuid",
        "event",
        schema="outbox",
        type_="unique",
    )

    op.drop_column("event", "event_type_id", schema="outbox")
    op.drop_column("event", "project_id", schema="outbox")
    op.drop_column("event", "event_uuid", schema="outbox")

    op.drop_table("event_type", schema="outbox")
    # ### end Alembic commands ###
