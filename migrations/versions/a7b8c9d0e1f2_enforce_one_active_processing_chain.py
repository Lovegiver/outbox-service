"""Enforce one active processing chain per EventType/schema scope.

Revision ID: a7b8c9d0e1f2
Revises: c6a1b2d3e4f5
Create Date: 2026-08-21
"""

from collections.abc import Sequence

from alembic import op


revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "c6a1b2d3e4f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the PostgreSQL last-resort active-scope invariant."""
    op.create_index(
        "uq_processing_chain_active_scope",
        "processing_chain",
        ["event_type_id", "schema_definition_id"],
        unique=True,
        schema="outbox",
        postgresql_where="is_active",
    )


def downgrade() -> None:
    """Remove the active-scope invariant without changing snapshot data."""
    op.drop_index(
        "uq_processing_chain_active_scope",
        table_name="processing_chain",
        schema="outbox",
    )
