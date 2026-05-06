"""Add HNSW index on memories.embedding for vector similarity search.

Revision ID: 0006_embedding_hnsw_index
Revises: 0005_repo_scope_layer
Create Date: 2026-05-06 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_embedding_hnsw_index"
down_revision = "0005_repo_scope_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Set embedding column dimension to 384 (all-MiniLM-L6-v2 / bge-small-en)
    op.execute(
        "ALTER TABLE memories ALTER COLUMN embedding TYPE vector(384) "
        "USING embedding::vector(384)"
    )
    # Create HNSW index — partial on active memories only
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memories_embedding_hnsw "
        "ON memories USING hnsw (embedding vector_cosine_ops) "
        "WHERE status = 'active'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding_hnsw")
    # Revert column to untyped vector
    op.execute(
        "ALTER TABLE memories ALTER COLUMN embedding TYPE vector "
        "USING embedding::vector"
    )
