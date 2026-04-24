"""initial memory schema

Revision ID: 0001_initial_memory_schema
Revises:
Create Date: 2026-04-23 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_memory_schema"
down_revision = None
branch_labels = None
depends_on = None


class Vector(sa.types.UserDefinedType):
    """Self-contained pgvector type for this historical migration."""

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
    return [
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name=f"ck_{table_name}_confidence"),
        sa.CheckConstraint("sensitivity IN ('normal', 'sensitive', 'private')", name=f"ck_{table_name}_sensitivity"),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'superseded', 'deleted')",
            name=f"ck_{table_name}_status",
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

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
        sa.PrimaryKeyConstraint("id", name="pk_entities"),
    )
    op.create_index("ix_entities_entity_type", "entities", ["entity_type"])
    op.create_index("ix_entities_name", "entities", ["name"])
    op.create_index("ix_entities_status", "entities", ["status"])

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
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], name="fk_memories_entity_id_entities", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["supersedes_memory_id"],
            ["memories.id"],
            name="fk_memories_supersedes_memory_id_memories",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_memories"),
    )
    op.create_index("ix_memories_entity_id", "memories", ["entity_id"])
    op.create_index("ix_memories_memory_type", "memories", ["memory_type"])
    op.create_index("ix_memories_status", "memories", ["status"])
    op.create_index("ix_memories_supersedes_memory_id", "memories", ["supersedes_memory_id"])

    op.create_table(
        "memory_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.String(128), nullable=False),
        sa.Column("attributes", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        *lifecycle_columns(),
        *timestamp_columns(),
        *lifecycle_checks("memory_tags"),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], name="fk_memory_tags_memory_id_memories", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_memory_tags"),
        sa.UniqueConstraint("memory_id", "tag", name="uq_memory_tags_memory_id_tag"),
    )
    op.create_index("ix_memory_tags_memory_id", "memory_tags", ["memory_id"])
    op.create_index("ix_memory_tags_tag", "memory_tags", ["tag"])
    op.create_index("ix_memory_tags_status", "memory_tags", ["status"])

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
            ["source_entity_id"],
            ["entities.id"],
            name="fk_relationships_source_entity_id_entities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["entities.id"],
            name="fk_relationships_target_entity_id_entities",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_relationship_id"],
            ["relationships.id"],
            name="fk_relationships_supersedes_relationship_id_relationships",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_relationships"),
    )
    op.create_index("ix_relationships_source_entity_id", "relationships", ["source_entity_id"])
    op.create_index("ix_relationships_target_entity_id", "relationships", ["target_entity_id"])
    op.create_index("ix_relationships_relationship_type", "relationships", ["relationship_type"])
    op.create_index("ix_relationships_status", "relationships", ["status"])

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
        sa.PrimaryKeyConstraint("id", name="pk_retrieval_profiles"),
        sa.UniqueConstraint("name", name="uq_retrieval_profiles_name"),
    )
    op.create_index("ix_retrieval_profiles_status", "retrieval_profiles", ["status"])

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
        sa.CheckConstraint(
            "token_estimate IS NULL OR token_estimate >= 0",
            name="ck_context_packets_token_estimate",
        ),
        sa.ForeignKeyConstraint(
            ["retrieval_profile_id"],
            ["retrieval_profiles.id"],
            name="fk_context_packets_retrieval_profile_id_retrieval_profiles",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_context_packet_id"],
            ["context_packets.id"],
            name="fk_context_packets_supersedes_context_packet_id_context_packets",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_context_packets"),
    )
    op.create_index("ix_context_packets_retrieval_profile_id", "context_packets", ["retrieval_profile_id"])
    op.create_index("ix_context_packets_status", "context_packets", ["status"])

    op.create_table(
        "context_packet_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("context_packet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("rank IS NULL OR rank >= 0", name="ck_context_packet_memories_rank"),
        sa.ForeignKeyConstraint(
            ["context_packet_id"],
            ["context_packets.id"],
            name="fk_context_packet_memories_context_packet_id_context_packets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["memory_id"],
            ["memories.id"],
            name="fk_context_packet_memories_memory_id_memories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_context_packet_memories"),
        sa.UniqueConstraint(
            "context_packet_id",
            "memory_id",
            name="uq_context_packet_memories_packet_memory",
        ),
    )
    op.create_index(
        "ix_context_packet_memories_context_packet_id",
        "context_packet_memories",
        ["context_packet_id"],
    )
    op.create_index("ix_context_packet_memories_memory_id", "context_packet_memories", ["memory_id"])

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
        sa.CheckConstraint(
            "status IN ('recorded', 'applied', 'reverted', 'failed')",
            name="ck_pruning_log_status",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_pruning_log_confidence",
        ),
        sa.CheckConstraint("sensitivity IN ('normal', 'sensitive', 'private')", name="ck_pruning_log_sensitivity"),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], name="fk_pruning_log_memory_id_memories", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_pruning_log"),
    )
    op.create_index("ix_pruning_log_memory_id", "pruning_log", ["memory_id"])
    op.create_index("ix_pruning_log_action", "pruning_log", ["action"])
    op.create_index("ix_pruning_log_status", "pruning_log", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pruning_log_status", table_name="pruning_log")
    op.drop_index("ix_pruning_log_action", table_name="pruning_log")
    op.drop_index("ix_pruning_log_memory_id", table_name="pruning_log")
    op.drop_table("pruning_log")

    op.drop_index("ix_context_packets_status", table_name="context_packets")
    op.drop_index("ix_context_packets_retrieval_profile_id", table_name="context_packets")

    op.drop_index("ix_context_packet_memories_memory_id", table_name="context_packet_memories")
    op.drop_index("ix_context_packet_memories_context_packet_id", table_name="context_packet_memories")
    op.drop_table("context_packet_memories")

    op.drop_table("context_packets")

    op.drop_index("ix_retrieval_profiles_status", table_name="retrieval_profiles")
    op.drop_table("retrieval_profiles")

    op.drop_index("ix_relationships_status", table_name="relationships")
    op.drop_index("ix_relationships_relationship_type", table_name="relationships")
    op.drop_index("ix_relationships_target_entity_id", table_name="relationships")
    op.drop_index("ix_relationships_source_entity_id", table_name="relationships")
    op.drop_table("relationships")

    op.drop_index("ix_memory_tags_status", table_name="memory_tags")
    op.drop_index("ix_memory_tags_tag", table_name="memory_tags")
    op.drop_index("ix_memory_tags_memory_id", table_name="memory_tags")
    op.drop_table("memory_tags")

    op.drop_index("ix_memories_supersedes_memory_id", table_name="memories")
    op.drop_index("ix_memories_status", table_name="memories")
    op.drop_index("ix_memories_memory_type", table_name="memories")
    op.drop_index("ix_memories_entity_id", table_name="memories")
    op.drop_table("memories")

    op.drop_index("ix_entities_status", table_name="entities")
    op.drop_index("ix_entities_name", table_name="entities")
    op.drop_index("ix_entities_entity_type", table_name="entities")
    op.drop_table("entities")
