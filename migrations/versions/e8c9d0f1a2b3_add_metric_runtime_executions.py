"""add durable metric runtime executions

Revision ID: e8c9d0f1a2b3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-25 21:10:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8c9d0f1a2b3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create targeted Event/snapshot and Event/plan execution records."""
    op.create_table(
        "metric_processing_execution",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("processing_chain_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["outbox.event.id"]),
        sa.ForeignKeyConstraint(
            ["processing_chain_id"], ["outbox.processing_chain.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_metric_processing_execution_event"),
        schema="outbox",
    )
    op.create_index(
        "ix_outbox_metric_processing_execution_event_id",
        "metric_processing_execution",
        ["event_id"],
        schema="outbox",
    )
    op.create_index(
        "ix_outbox_metric_processing_execution_processing_chain_id",
        "metric_processing_execution",
        ["processing_chain_id"],
        schema="outbox",
    )

    op.create_table(
        "metric_plan_execution",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("metric_processing_execution_id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("processing_chain_id", sa.BigInteger(), nullable=False),
        sa.Column("processing_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("is_retryable", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["outbox.event.id"]),
        sa.ForeignKeyConstraint(
            ["metric_processing_execution_id"],
            ["outbox.metric_processing_execution.id"],
        ),
        sa.ForeignKeyConstraint(
            ["processing_chain_id"], ["outbox.processing_chain.id"]
        ),
        sa.ForeignKeyConstraint(["processing_plan_id"], ["outbox.processing_plan.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "processing_plan_id",
            name="uq_metric_plan_execution_event_plan",
        ),
        schema="outbox",
    )
    for column in (
        "metric_processing_execution_id",
        "event_id",
        "processing_chain_id",
        "processing_plan_id",
    ):
        op.create_index(
            f"ix_outbox_metric_plan_execution_{column}",
            "metric_plan_execution",
            [column],
            schema="outbox",
        )
    op.create_index(
        "ix_metric_plan_execution_retry_schedule",
        "metric_plan_execution",
        ["status", "next_attempt_at", "created_at", "id"],
        schema="outbox",
    )

    op.add_column(
        "analytical_observation",
        sa.Column("processing_chain_id", sa.BigInteger(), nullable=True),
        schema="outbox",
    )
    op.add_column(
        "analytical_observation",
        sa.Column("processing_plan_id", sa.BigInteger(), nullable=True),
        schema="outbox",
    )
    op.add_column(
        "analytical_observation",
        sa.Column("metric_plan_execution_id", sa.BigInteger(), nullable=True),
        schema="outbox",
    )
    op.add_column(
        "analytical_observation",
        sa.Column("observation_key", sa.String(length=255), nullable=True),
        schema="outbox",
    )
    op.create_foreign_key(
        "fk_analytical_observation_processing_chain",
        "analytical_observation",
        "processing_chain",
        ["processing_chain_id"],
        ["id"],
        source_schema="outbox",
        referent_schema="outbox",
    )
    op.create_foreign_key(
        "fk_analytical_observation_processing_plan",
        "analytical_observation",
        "processing_plan",
        ["processing_plan_id"],
        ["id"],
        source_schema="outbox",
        referent_schema="outbox",
    )
    op.create_foreign_key(
        "fk_analytical_observation_metric_plan_execution",
        "analytical_observation",
        "metric_plan_execution",
        ["metric_plan_execution_id"],
        ["id"],
        source_schema="outbox",
        referent_schema="outbox",
    )
    for column in (
        "processing_chain_id",
        "processing_plan_id",
        "metric_plan_execution_id",
    ):
        op.create_index(
            f"ix_outbox_analytical_observation_{column}",
            "analytical_observation",
            [column],
            schema="outbox",
        )
    op.create_unique_constraint(
        "uq_analytical_observation_runtime_identity",
        "analytical_observation",
        ["event_id", "processing_plan_id", "observation_key"],
        schema="outbox",
    )


def downgrade() -> None:
    """Remove runtime execution metadata while preserving older migrations."""
    op.drop_constraint(
        "uq_analytical_observation_runtime_identity",
        "analytical_observation",
        schema="outbox",
        type_="unique",
    )
    for column in (
        "metric_plan_execution_id",
        "processing_plan_id",
        "processing_chain_id",
    ):
        op.drop_index(
            f"ix_outbox_analytical_observation_{column}",
            table_name="analytical_observation",
            schema="outbox",
        )
    for constraint in (
        "fk_analytical_observation_metric_plan_execution",
        "fk_analytical_observation_processing_plan",
        "fk_analytical_observation_processing_chain",
    ):
        op.drop_constraint(
            constraint,
            "analytical_observation",
            schema="outbox",
            type_="foreignkey",
        )
    for column in (
        "observation_key",
        "metric_plan_execution_id",
        "processing_plan_id",
        "processing_chain_id",
    ):
        op.drop_column("analytical_observation", column, schema="outbox")

    op.drop_index(
        "ix_metric_plan_execution_retry_schedule",
        table_name="metric_plan_execution",
        schema="outbox",
    )
    for column in (
        "processing_plan_id",
        "processing_chain_id",
        "event_id",
        "metric_processing_execution_id",
    ):
        op.drop_index(
            f"ix_outbox_metric_plan_execution_{column}",
            table_name="metric_plan_execution",
            schema="outbox",
        )
    op.drop_table("metric_plan_execution", schema="outbox")
    op.drop_index(
        "ix_outbox_metric_processing_execution_processing_chain_id",
        table_name="metric_processing_execution",
        schema="outbox",
    )
    op.drop_index(
        "ix_outbox_metric_processing_execution_event_id",
        table_name="metric_processing_execution",
        schema="outbox",
    )
    op.drop_table("metric_processing_execution", schema="outbox")
