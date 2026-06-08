"""add_correlation_id_to_event

Revision ID: d8f346bd8965
Revises: 347082a348b9
Create Date: 2026-06-08 15:04:01.959586

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f346bd8965'
down_revision: Union[str, Sequence[str], None] = '347082a348b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event",
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
        schema="outbox",
    )
    op.create_index(
        "ix_outbox_event_correlation_id",
        "event",
        ["correlation_id"],
        unique=False,
        schema="outbox",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outbox_event_correlation_id",
        table_name="event",
        schema="outbox",
    )
    op.drop_column(
        "event",
        "correlation_id",
        schema="outbox",
    )
