"""add route authentication fields

Revision ID: 88391a903eb5
Revises: e143e4542c16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "88391a903eb5"
down_revision: Union[str, Sequence[str], None] = "e143e4542c16"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column(
        "route_definition",
        sa.Column(
            "auth_type",
            sa.String(30),
            nullable=False,
            server_default="NONE",
        ),
        schema="outbox",
    )

    op.add_column(
        "route_definition",
        sa.Column(
            "auth_config",
            sa.JSON(),
            nullable=True,
        ),
        schema="outbox",
    )

    op.add_column(
        "route_definition",
        sa.Column(
            "secret_ref",
            sa.String(255),
            nullable=True,
        ),
        schema="outbox",
    )


def downgrade() -> None:

    op.drop_column(
        "route_definition",
        "secret_ref",
        schema="outbox",
    )

    op.drop_column(
        "route_definition",
        "auth_config",
        schema="outbox",
    )

    op.drop_column(
        "route_definition",
        "auth_type",
        schema="outbox",
    )
