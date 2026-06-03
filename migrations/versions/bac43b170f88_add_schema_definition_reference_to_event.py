"""add schema definition reference to event

Revision ID: bac43b170f88
Revises: 4de751cd9de2
Create Date: 2026-06-02 17:57:20.772971

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bac43b170f88'
down_revision: Union[str, Sequence[str], None] = '4de751cd9de2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event",
        sa.Column("schema_definition_id", sa.BigInteger(), nullable=True),
        schema="outbox",
    )

    op.create_foreign_key(
        "fk_event_schema_definition",
        "event",
        "schema_definition",
        ["schema_definition_id"],
        ["id"],
        source_schema="outbox",
        referent_schema="outbox",
    )

    op.execute(
        """
        UPDATE outbox.event e
        SET schema_definition_id = s.id
        FROM outbox.schema_definition s
        WHERE s.event_type_id = e.event_type_id
          AND s.json_version_internal = e.json_version_internal
        """
    )

    op.alter_column(
        "event",
        "schema_definition_id",
        nullable=False,
        schema="outbox",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_event_schema_definition",
        "event",
        schema="outbox",
        type_="foreignkey",
    )

    op.drop_column(
        "event",
        "schema_definition_id",
        schema="outbox",
    )
