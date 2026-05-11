"""Add code_citations JSONB column to memories.

Revision ID: 0007_code_citations
Revises: 0006_embedding_hnsw_index
Create Date: 2026-05-11
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_code_citations"
down_revision = "0006_embedding_hnsw_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memories",
        sa.Column("code_citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_memories_code_citations_gin",
        "memories",
        ["code_citations"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_memories_code_citations_gin", table_name="memories")
    op.drop_column("memories", "code_citations")
