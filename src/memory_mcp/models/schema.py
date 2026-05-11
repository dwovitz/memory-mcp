"""Structured memory database models."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    literal_column,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from memory_mcp.models.base import Base
from memory_mcp.models.types import Vector

JsonDict = dict[str, Any]
JsonList = list[Any]

ACTIVE_STATUS_CHECK = "status IN ('active', 'archived', 'superseded', 'deleted')"
SENSITIVITY_CHECK = "sensitivity IN ('normal', 'sensitive', 'private')"


class TimestampMixin:
    """Created/updated timestamps for mutable records."""

    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class LifecycleMixin:
    """Common lifecycle, confidence, sensitivity, and scope fields."""

    confidence: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("1.0"),
    )
    sensitivity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'normal'"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'active'"),
    )
    applies_to: Mapped[JsonDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class Entity(TimestampMixin, LifecycleMixin, Base):
    """A person, medication, app, media item, preference area, or other subject."""

    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_entities_confidence"),
        CheckConstraint(SENSITIVITY_CHECK, name="ck_entities_sensitivity"),
        CheckConstraint(ACTIVE_STATUS_CHECK, name="ck_entities_status"),
        Index("ix_entities_entity_type", "entity_type"),
        Index("ix_entities_name", "name"),
        Index("ix_entities_status", "status"),
        Index("ix_entities_type_status_name", "entity_type", "status", "name"),
        Index(
            "ix_entities_aliases_gin",
            "aliases",
            postgresql_using="gin",
            postgresql_ops={"aliases": "jsonb_path_ops"},
        ),
        Index(
            "ix_entities_attributes_gin",
            "attributes",
            postgresql_using="gin",
            postgresql_ops={"attributes": "jsonb_path_ops"},
        ),
        Index(
            "ix_entities_applies_to_gin",
            "applies_to",
            postgresql_using="gin",
            postgresql_ops={"applies_to": "jsonb_path_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[JsonList] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    attributes: Mapped[JsonDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class Memory(TimestampMixin, LifecycleMixin, Base):
    """A remembered fact, preference, event, observation, or summary."""

    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_memories_confidence"),
        CheckConstraint(SENSITIVITY_CHECK, name="ck_memories_sensitivity"),
        CheckConstraint(ACTIVE_STATUS_CHECK, name="ck_memories_status"),
        Index("ix_memories_entity_id", "entity_id"),
        Index("ix_memories_memory_type", "memory_type"),
        Index("ix_memories_status", "status"),
        Index("ix_memories_supersedes_memory_id", "supersedes_memory_id"),
        Index("ix_memories_status_sensitivity_type_created", "status", "sensitivity", "memory_type", "created_at"),
        Index("ix_memories_entity_status_created", "entity_id", "status", "created_at"),
        Index(
            "ix_memories_evidence_gin",
            "evidence",
            postgresql_using="gin",
            postgresql_ops={"evidence": "jsonb_path_ops"},
        ),
        Index(
            "ix_memories_metadata_gin",
            "metadata",
            postgresql_using="gin",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
        Index(
            "ix_memories_applies_to_gin",
            "applies_to",
            postgresql_using="gin",
            postgresql_ops={"applies_to": "jsonb_path_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    entity_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="SET NULL"),
        nullable=True,
    )
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[JsonList] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    metadata_: Mapped[JsonDict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    embedding: Mapped[Any | None] = mapped_column(
        Vector(),
        nullable=True,
        comment=(
            "pgvector embedding placeholder. After choosing a fixed embedding "
            "dimension, create an HNSW index with vector_cosine_ops."
        ),
    )
    supersedes_memory_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    superseded_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    code_citations: Mapped[JsonList | None] = mapped_column(JSONB, nullable=True)


Index(
    "ix_memories_full_text_search",
    func.to_tsvector(
        literal_column("'english'"),
        func.coalesce(Memory.content, literal_column("''"))
        + literal_column("' '")
        + func.coalesce(Memory.summary, literal_column("''")),
    ),
    postgresql_using="gin",
)


class MemoryTag(TimestampMixin, LifecycleMixin, Base):
    """A tag attached to a memory for structured filtering."""

    __tablename__ = "memory_tags"
    __table_args__ = (
        UniqueConstraint("memory_id", "tag", name="uq_memory_tags_memory_id_tag"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_memory_tags_confidence"),
        CheckConstraint(SENSITIVITY_CHECK, name="ck_memory_tags_sensitivity"),
        CheckConstraint(ACTIVE_STATUS_CHECK, name="ck_memory_tags_status"),
        Index("ix_memory_tags_memory_id", "memory_id"),
        Index("ix_memory_tags_tag", "tag"),
        Index("ix_memory_tags_status", "status"),
        Index("ix_memory_tags_tag_status_memory", "tag", "status", "memory_id"),
        Index(
            "ix_memory_tags_attributes_gin",
            "attributes",
            postgresql_using="gin",
            postgresql_ops={"attributes": "jsonb_path_ops"},
        ),
        Index(
            "ix_memory_tags_applies_to_gin",
            "applies_to",
            postgresql_using="gin",
            postgresql_ops={"applies_to": "jsonb_path_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    memory_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag: Mapped[str] = mapped_column(String(128), nullable=False)
    attributes: Mapped[JsonDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class Relationship(TimestampMixin, LifecycleMixin, Base):
    """A typed relationship between two entities."""

    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_relationships_confidence"),
        CheckConstraint(SENSITIVITY_CHECK, name="ck_relationships_sensitivity"),
        CheckConstraint(ACTIVE_STATUS_CHECK, name="ck_relationships_status"),
        Index("ix_relationships_source_entity_id", "source_entity_id"),
        Index("ix_relationships_target_entity_id", "target_entity_id"),
        Index("ix_relationships_relationship_type", "relationship_type"),
        Index("ix_relationships_status", "status"),
        Index("ix_relationships_source_type_status", "source_entity_id", "relationship_type", "status"),
        Index("ix_relationships_target_type_status", "target_entity_id", "relationship_type", "status"),
        Index(
            "ix_relationships_evidence_gin",
            "evidence",
            postgresql_using="gin",
            postgresql_ops={"evidence": "jsonb_path_ops"},
        ),
        Index(
            "ix_relationships_metadata_gin",
            "metadata",
            postgresql_using="gin",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
        Index(
            "ix_relationships_applies_to_gin",
            "applies_to",
            postgresql_using="gin",
            postgresql_ops={"applies_to": "jsonb_path_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_entity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_entity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[JsonList] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    metadata_: Mapped[JsonDict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    supersedes_relationship_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("relationships.id", ondelete="SET NULL"),
        nullable=True,
    )


class RetrievalProfile(TimestampMixin, LifecycleMixin, Base):
    """Named retrieval configuration for future context assembly."""

    __tablename__ = "retrieval_profiles"
    __table_args__ = (
        UniqueConstraint("name", name="uq_retrieval_profiles_name"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_retrieval_profiles_confidence"),
        CheckConstraint(SENSITIVITY_CHECK, name="ck_retrieval_profiles_sensitivity"),
        CheckConstraint(ACTIVE_STATUS_CHECK, name="ck_retrieval_profiles_status"),
        Index("ix_retrieval_profiles_status", "status"),
        Index(
            "ix_retrieval_profiles_query_config_gin",
            "query_config",
            postgresql_using="gin",
            postgresql_ops={"query_config": "jsonb_path_ops"},
        ),
        Index(
            "ix_retrieval_profiles_filters_gin",
            "filters",
            postgresql_using="gin",
            postgresql_ops={"filters": "jsonb_path_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_config: Mapped[JsonDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    filters: Mapped[JsonDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class ContextPacket(TimestampMixin, LifecycleMixin, Base):
    """A compact generated context packet for prompt use."""

    __tablename__ = "context_packets"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_context_packets_confidence"),
        CheckConstraint(SENSITIVITY_CHECK, name="ck_context_packets_sensitivity"),
        CheckConstraint(ACTIVE_STATUS_CHECK, name="ck_context_packets_status"),
        CheckConstraint(
            "token_estimate IS NULL OR token_estimate >= 0",
            name="ck_context_packets_token_estimate",
        ),
        Index("ix_context_packets_retrieval_profile_id", "retrieval_profile_id"),
        Index("ix_context_packets_status", "status"),
        Index("ix_context_packets_status_expires", "status", "expires_at"),
        Index(
            "ix_context_packets_metadata_gin",
            "metadata",
            postgresql_using="gin",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
        Index(
            "ix_context_packets_applies_to_gin",
            "applies_to",
            postgresql_using="gin",
            postgresql_ops={"applies_to": "jsonb_path_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    retrieval_profile_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("retrieval_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[JsonDict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    supersedes_context_packet_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("context_packets.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContextPacketMemory(Base):
    """Foreign-key-backed source memory provenance for context packets."""

    __tablename__ = "context_packet_memories"
    __table_args__ = (
        UniqueConstraint(
            "context_packet_id",
            "memory_id",
            name="uq_context_packet_memories_packet_memory",
        ),
        CheckConstraint("rank IS NULL OR rank >= 0", name="ck_context_packet_memories_rank"),
        Index("ix_context_packet_memories_context_packet_id", "context_packet_id"),
        Index("ix_context_packet_memories_memory_id", "memory_id"),
        Index("ix_context_packet_memories_memory_rank", "memory_id", "rank"),
        Index(
            "ix_context_packet_memories_metadata_gin",
            "metadata",
            postgresql_using="gin",
            postgresql_ops={"metadata": "jsonb_path_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    context_packet_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("context_packets.id", ondelete="CASCADE"),
        nullable=False,
    )
    memory_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[JsonDict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PruningLog(Base):
    """Audit log for future memory pruning decisions."""

    __tablename__ = "pruning_log"
    __table_args__ = (
        CheckConstraint(
            "status IN ('recorded', 'applied', 'reverted', 'failed')",
            name="ck_pruning_log_status",
        ),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_pruning_log_confidence"),
        CheckConstraint(SENSITIVITY_CHECK, name="ck_pruning_log_sensitivity"),
        Index("ix_pruning_log_memory_id", "memory_id"),
        Index("ix_pruning_log_action", "action"),
        Index("ix_pruning_log_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    memory_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    sensitivity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'normal'"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'recorded'"),
    )
    applies_to: Mapped[JsonDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    before_state: Mapped[JsonDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    after_state: Mapped[JsonDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    metadata_: Mapped[JsonDict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AuditEvent(Base):
    """Provider-neutral security audit event without sensitive payloads."""

    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("decision IN ('allow', 'deny', 'success', 'failure')", name="ck_audit_events_decision"),
        Index("ix_audit_events_created_at", "created_at"),
        Index("ix_audit_events_actor_subject", "actor_subject"),
        Index("ix_audit_events_tool_action", "tool_name", "action"),
        Index("ix_audit_events_tenant_id", "tenant_id"),
        Index(
            "ix_audit_events_resource_scope_gin",
            "resource_scope",
            postgresql_using="gin",
            postgresql_ops={"resource_scope": "jsonb_path_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    actor_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    principal_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_scope: Mapped[JsonDict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[JsonDict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
