"""add retrieval indexes

Revision ID: 0002_retrieval_indexes
Revises: 0001_initial_memory_schema
Create Date: 2026-04-23 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "0002_retrieval_indexes"
down_revision = "0001_initial_memory_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Composite B-tree indexes for common structured retrieval filters.
    op.create_index(
        "ix_entities_type_status_name",
        "entities",
        ["entity_type", "status", "name"],
    )
    op.create_index(
        "ix_memories_status_sensitivity_type_created",
        "memories",
        ["status", "sensitivity", "memory_type", "created_at"],
    )
    op.create_index(
        "ix_memories_entity_status_created",
        "memories",
        ["entity_id", "status", "created_at"],
    )
    op.create_index(
        "ix_memory_tags_tag_status_memory",
        "memory_tags",
        ["tag", "status", "memory_id"],
    )
    op.create_index(
        "ix_relationships_source_type_status",
        "relationships",
        ["source_entity_id", "relationship_type", "status"],
    )
    op.create_index(
        "ix_relationships_target_type_status",
        "relationships",
        ["target_entity_id", "relationship_type", "status"],
    )
    op.create_index(
        "ix_context_packets_status_expires",
        "context_packets",
        ["status", "expires_at"],
    )
    op.create_index(
        "ix_context_packet_memories_memory_rank",
        "context_packet_memories",
        ["memory_id", "rank"],
    )

    # JSONB GIN indexes for containment/path filters used by structured retrieval.
    op.create_index(
        "ix_entities_aliases_gin",
        "entities",
        ["aliases"],
        postgresql_using="gin",
        postgresql_ops={"aliases": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_entities_attributes_gin",
        "entities",
        ["attributes"],
        postgresql_using="gin",
        postgresql_ops={"attributes": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_entities_applies_to_gin",
        "entities",
        ["applies_to"],
        postgresql_using="gin",
        postgresql_ops={"applies_to": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_memories_evidence_gin",
        "memories",
        ["evidence"],
        postgresql_using="gin",
        postgresql_ops={"evidence": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_memories_metadata_gin",
        "memories",
        ["metadata"],
        postgresql_using="gin",
        postgresql_ops={"metadata": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_memories_applies_to_gin",
        "memories",
        ["applies_to"],
        postgresql_using="gin",
        postgresql_ops={"applies_to": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_memory_tags_attributes_gin",
        "memory_tags",
        ["attributes"],
        postgresql_using="gin",
        postgresql_ops={"attributes": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_memory_tags_applies_to_gin",
        "memory_tags",
        ["applies_to"],
        postgresql_using="gin",
        postgresql_ops={"applies_to": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_relationships_evidence_gin",
        "relationships",
        ["evidence"],
        postgresql_using="gin",
        postgresql_ops={"evidence": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_relationships_metadata_gin",
        "relationships",
        ["metadata"],
        postgresql_using="gin",
        postgresql_ops={"metadata": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_relationships_applies_to_gin",
        "relationships",
        ["applies_to"],
        postgresql_using="gin",
        postgresql_ops={"applies_to": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_retrieval_profiles_query_config_gin",
        "retrieval_profiles",
        ["query_config"],
        postgresql_using="gin",
        postgresql_ops={"query_config": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_retrieval_profiles_filters_gin",
        "retrieval_profiles",
        ["filters"],
        postgresql_using="gin",
        postgresql_ops={"filters": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_context_packets_metadata_gin",
        "context_packets",
        ["metadata"],
        postgresql_using="gin",
        postgresql_ops={"metadata": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_context_packets_applies_to_gin",
        "context_packets",
        ["applies_to"],
        postgresql_using="gin",
        postgresql_ops={"applies_to": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_context_packet_memories_metadata_gin",
        "context_packet_memories",
        ["metadata"],
        postgresql_using="gin",
        postgresql_ops={"metadata": "jsonb_path_ops"},
    )

    # Full-text GIN index for lexical memory search.
    op.execute(
        """
        CREATE INDEX ix_memories_full_text_search
        ON memories
        USING gin (
            to_tsvector(
                'english',
                coalesce(content, '') || ' ' || coalesce(summary, '')
            )
        )
        """
    )

    # Vector search plan: the embedding column is dimensionless until a model is chosen.
    # Once fixed, prefer HNSW with cosine distance, for example:
    # ALTER TABLE memories ALTER COLUMN embedding TYPE vector(1536);
    # CREATE INDEX ix_memories_embedding_hnsw_cosine
    #     ON memories USING hnsw (embedding vector_cosine_ops)
    #     WHERE embedding IS NOT NULL;
    op.execute(
        """
        COMMENT ON COLUMN memories.embedding IS
        'pgvector embedding placeholder. After choosing a fixed embedding dimension, create an HNSW index with vector_cosine_ops.'
        """
    )


def downgrade() -> None:
    op.execute("COMMENT ON COLUMN memories.embedding IS NULL")

    op.execute("DROP INDEX IF EXISTS ix_memories_full_text_search")

    op.drop_index("ix_context_packet_memories_metadata_gin", table_name="context_packet_memories")
    op.drop_index("ix_context_packets_applies_to_gin", table_name="context_packets")
    op.drop_index("ix_context_packets_metadata_gin", table_name="context_packets")
    op.drop_index("ix_retrieval_profiles_filters_gin", table_name="retrieval_profiles")
    op.drop_index("ix_retrieval_profiles_query_config_gin", table_name="retrieval_profiles")
    op.drop_index("ix_relationships_applies_to_gin", table_name="relationships")
    op.drop_index("ix_relationships_metadata_gin", table_name="relationships")
    op.drop_index("ix_relationships_evidence_gin", table_name="relationships")
    op.drop_index("ix_memory_tags_applies_to_gin", table_name="memory_tags")
    op.drop_index("ix_memory_tags_attributes_gin", table_name="memory_tags")
    op.drop_index("ix_memories_applies_to_gin", table_name="memories")
    op.drop_index("ix_memories_metadata_gin", table_name="memories")
    op.drop_index("ix_memories_evidence_gin", table_name="memories")
    op.drop_index("ix_entities_applies_to_gin", table_name="entities")
    op.drop_index("ix_entities_attributes_gin", table_name="entities")
    op.drop_index("ix_entities_aliases_gin", table_name="entities")

    op.drop_index("ix_context_packet_memories_memory_rank", table_name="context_packet_memories")
    op.drop_index("ix_context_packets_status_expires", table_name="context_packets")
    op.drop_index("ix_relationships_target_type_status", table_name="relationships")
    op.drop_index("ix_relationships_source_type_status", table_name="relationships")
    op.drop_index("ix_memory_tags_tag_status_memory", table_name="memory_tags")
    op.drop_index("ix_memories_entity_status_created", table_name="memories")
    op.drop_index("ix_memories_status_sensitivity_type_created", table_name="memories")
    op.drop_index("ix_entities_type_status_name", table_name="entities")
