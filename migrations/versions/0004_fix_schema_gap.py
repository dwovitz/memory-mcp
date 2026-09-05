"""create missing tables after schema reset

Revision ID: 0004_fix_schema_gap
Revises: 0003_audit_events
Create Date: 2026-05-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_fix_schema_gap"
down_revision = "0003_audit_events"
branch_labels = None
depends_on = None


class Vector(sa.types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_: object) -> str:
        return "vector"


def lifecycle_columns() -> list[sa.Column]:
    return [
        sa.Column("confidence", sa.Numeric(4, 3), server_default=sa.text("1.0"), nullable=False),
        sa.Column("sensitivity", sa.String(32), server_default=sa.text("'normal'"), nullable=False),
        sa.Column("status", sa.String(32), server_default=sa.text("'active'"), nullable=False),
        sa.Column("applies_to", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    ]


def timestamp_columns(include_updated_at: bool = True) -> list[sa.Column]:
    columns = [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]
    if include_updated_at:
        columns.append(
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        )
    return columns


def lifecycle_checks(table_name: str) -> list[sa.CheckConstraint]:
    # Use _v2 suffix to avoid clashing with _legacy table constraints of the same name
    return [
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name=f"ck_{table_name}_confidence_v2"),
        sa.CheckConstraint("sensitivity IN ('normal', 'sensitive', 'private')", name=f"ck_{table_name}_sensitivity_v2"),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'superseded', 'deleted')",
            name=f"ck_{table_name}_status_v2",
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # MIG-001 fix: this migration's docstring says "create missing tables after schema reset" —
    # i.e. it assumes 0001-0003's versions of these tables were already dropped out-of-band before
    # it runs. That never happens on a fresh database (this one included): 0001-0003 create the
    # old-constraint-name versions moments earlier in this same `alembic upgrade head` invocation,
    # so this unconditional op.create_table() hit DuplicateTable and rolled back the whole run.
    # Dropping them here first makes the migration do what its own docstring says on every
    # environment, fresh or previously-reset alike. Order matches downgrade()'s drop order
    # (dependents before what they reference). Already-migrated environments never re-run this
    # upgrade(), so this is safe for them too.
    op.execute("DROP TABLE IF EXISTS pruning_log CASCADE")
    op.execute("DROP TABLE IF EXISTS context_packet_memories CASCADE")
    op.execute("DROP TABLE IF EXISTS context_packets CASCADE")
    op.execute("DROP TABLE IF EXISTS retrieval_profiles CASCADE")
    op.execute("DROP TABLE IF EXISTS relationships CASCADE")
    op.execute("DROP TABLE IF EXISTS memory_tags CASCADE")
    op.execute("DROP TABLE IF EXISTS memories CASCADE")
    op.execute("DROP TABLE IF EXISTS entities CASCADE")

    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("aliases", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        *lifecycle_columns(),
        *timestamp_columns(),
        *lifecycle_checks("entities"),
        sa.PrimaryKeyConstraint("id", name="pk_entities_v2"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_entities_entity_type ON entities (entity_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_entities_name ON entities (name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_entities_status ON entities (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_entities_type_status_name ON entities (entity_type, status, name)")

    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("memory_type", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("embedding", Vector(), nullable=True),
        sa.Column("supersedes_memory_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        *lifecycle_columns(),
        *timestamp_columns(),
        *lifecycle_checks("memories"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], name="fk_memories_entity_id_entities_v2", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["supersedes_memory_id"],
            ["memories.id"],
            name="fk_memories_supersedes_memory_id_memories_v2",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_memories_v2"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_memories_entity_id ON memories (entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memories_memory_type ON memories (memory_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memories_status ON memories (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memories_supersedes_memory_id ON memories (supersedes_memory_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memories_status_sensitivity_type_created ON memories (status, sensitivity, memory_type, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memories_entity_status_created ON memories (entity_id, status, created_at)")

    op.create_table(
        "memory_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        *lifecycle_columns(),
        *timestamp_columns(),
        *lifecycle_checks("memory_tags"),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], name="fk_memory_tags_memory_id_memories_v2", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_memory_tags_v2"),
        sa.UniqueConstraint("memory_id", "tag", name="uq_memory_tags_memory_id_tag_v2"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_memory_tags_memory_id ON memory_tags (memory_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memory_tags_tag ON memory_tags (tag)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memory_tags_status ON memory_tags (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memory_tags_tag_status_memory ON memory_tags (tag, status, memory_id)")

    op.create_table(
        "relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("supersedes_relationship_id", postgresql.UUID(as_uuid=True), nullable=True),
        *lifecycle_columns(),
        *timestamp_columns(),
        *lifecycle_checks("relationships"),
        sa.ForeignKeyConstraint(
            ["source_entity_id"], ["entities.id"],
            name="fk_relationships_source_entity_id_entities_v2", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"], ["entities.id"],
            name="fk_relationships_target_entity_id_entities_v2", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_relationship_id"], ["relationships.id"],
            name="fk_relationships_supersedes_relationship_id_relationships_v2", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_relationships_v2"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_relationships_source_entity_id ON relationships (source_entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_relationships_target_entity_id ON relationships (target_entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_relationships_relationship_type ON relationships (relationship_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_relationships_status ON relationships (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_relationships_source_type_status ON relationships (source_entity_id, relationship_type, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_relationships_target_type_status ON relationships (target_entity_id, relationship_type, status)")

    op.create_table(
        "retrieval_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("query_config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("filters", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        *lifecycle_columns(),
        *timestamp_columns(),
        *lifecycle_checks("retrieval_profiles"),
        sa.PrimaryKeyConstraint("id", name="pk_retrieval_profiles_v2"),
        sa.UniqueConstraint("name", name="uq_retrieval_profiles_name_v2"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_retrieval_profiles_status ON retrieval_profiles (status)")

    op.create_table(
        "context_packets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("retrieval_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("supersedes_context_packet_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *lifecycle_columns(),
        *timestamp_columns(),
        *lifecycle_checks("context_packets"),
        sa.CheckConstraint("token_estimate IS NULL OR token_estimate >= 0", name="ck_context_packets_token_estimate_v2"),
        sa.ForeignKeyConstraint(
            ["retrieval_profile_id"], ["retrieval_profiles.id"],
            name="fk_ctx_pkts_retrieval_profile_id_v2", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_context_packet_id"], ["context_packets.id"],
            name="fk_ctx_pkts_supersedes_ctx_pkt_id_v2", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_context_packets_v2"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_context_packets_retrieval_profile_id ON context_packets (retrieval_profile_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_context_packets_status ON context_packets (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_context_packets_status_expires ON context_packets (status, expires_at)")

    op.create_table(
        "context_packet_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("context_packet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("rank IS NULL OR rank >= 0", name="ck_context_packet_memories_rank_v2"),
        sa.ForeignKeyConstraint(
            ["context_packet_id"], ["context_packets.id"],
            name="fk_cpm_context_packet_id_v2", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"], ["memories.id"],
            name="fk_cpm_memory_id_memories_v2", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_context_packet_memories_v2"),
        sa.UniqueConstraint("context_packet_id", "memory_id", name="uq_context_packet_memories_packet_memory_v2"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_context_packet_memories_context_packet_id ON context_packet_memories (context_packet_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_context_packet_memories_memory_id ON context_packet_memories (memory_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_context_packet_memories_memory_rank ON context_packet_memories (memory_id, rank)")

    op.create_table(
        "pruning_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("sensitivity", sa.String(32), server_default=sa.text("'normal'"), nullable=False),
        sa.Column("status", sa.String(32), server_default=sa.text("'recorded'"), nullable=False),
        sa.Column("applies_to", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("before_state", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("after_state", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        *timestamp_columns(include_updated_at=False),
        sa.CheckConstraint("status IN ('recorded', 'applied', 'reverted', 'failed')", name="ck_pruning_log_status_v2"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_pruning_log_confidence_v2"),
        sa.CheckConstraint("sensitivity IN ('normal', 'sensitive', 'private')", name="ck_pruning_log_sensitivity_v2"),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], name="fk_pruning_log_memory_id_memories_v2", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_pruning_log_v2"),
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_pruning_log_memory_id ON pruning_log (memory_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pruning_log_action ON pruning_log (action)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pruning_log_status ON pruning_log (status)")

    # FTS index on memories content
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memories_full_text_search ON memories "
        "USING gin(to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.drop_table("pruning_log")
    op.drop_table("context_packet_memories")
    op.drop_table("context_packets")
    op.drop_table("retrieval_profiles")
    op.drop_table("relationships")
    op.drop_table("memory_tags")
    op.drop_table("memories")
    op.drop_table("entities")
