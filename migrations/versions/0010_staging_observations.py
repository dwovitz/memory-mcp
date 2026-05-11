"""staging_observations queue for raw session events.

Revision ID: 0010_staging_observations
Revises: 0007_code_citations
Create Date: 2026-05-11
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_staging_observations"
down_revision = "0007_code_citations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staging_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("scope", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_staging_obs_pending_created",
        "staging_observations",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_check_constraint(
        "ck_staging_obs_status",
        "staging_observations",
        "status IN ('pending', 'claimed', 'done', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_staging_obs_status", "staging_observations")
    op.drop_index("ix_staging_obs_pending_created", "staging_observations")
    op.drop_table("staging_observations")
