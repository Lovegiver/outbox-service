"""add compiled plan JSON to the processing plan

Revision ID: f6e6b51d5685
Revises: d8f346bd8965
Create Date: 2026-06-16 11:05:54.589693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f6e6b51d5685'
down_revision: Union[str, Sequence[str], None] = 'd8f346bd8965'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "processing_plan",
        sa.Column(
            "compiled_plan_json",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        schema="outbox",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(
        "processing_plan",
        "compiled_plan_json",
        schema="outbox",
    )
