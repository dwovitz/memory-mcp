"""Service layer for core memory operations."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from memory_mcp.models import Entity, Memory, MemoryTag, Relationship
from memory_mcp.repositories import EntityRepository, MemoryRepository, RelationshipRepository
from memory_mcp.scopes import (
    COMPONENT_MEMORY_SCOPE,
    GLOBAL_MEMORY_SCOPE,
    PROJECT_MEMORY_SCOPE,
    WORKSPACE_MEMORY_SCOPE,
    with_memory_scope,
)


class MemoryService:
    """Application-facing API for basic structured memory operations."""

    def __init__(self, session: Session) -> None:
        self.entities = EntityRepository(session)
        self.memories = MemoryRepository(session)
        self.relationships = RelationshipRepository(session)

    def create_entity(
        self,
        *,
        entity_type: str,
        name: str,
        aliases: list[Any] | None = None,
        attributes: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        status: str = "active",
        applies_to: dict[str, Any] | None = None,
    ) -> Entity:
        return self.entities.create(
            entity_type=entity_type,
            name=name,
            aliases=aliases,
            attributes=attributes,
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=applies_to,
        )

    def create_memory(
        self,
        *,
        memory_type: str,
        content: str,
        entity_id: UUID | None = None,
        summary: str | None = None,
        evidence: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        status: str = "active",
        applies_to: dict[str, Any] | None = None,
    ) -> Memory:
        return self.memories.create(
            entity_id=entity_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=applies_to,
        )

    def create_global_memory(
        self,
        *,
        memory_type: str,
        content: str,
        entity_id: UUID | None = None,
        summary: str | None = None,
        evidence: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        status: str = "active",
        applies_to: dict[str, Any] | None = None,
    ) -> Memory:
        return self.create_memory(
            entity_id=entity_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=with_memory_scope(
                applies_to,
                memory_scope=GLOBAL_MEMORY_SCOPE,
            ),
        )

    def create_project_memory(
        self,
        project: str,
        *,
        memory_type: str,
        content: str,
        entity_id: UUID | None = None,
        summary: str | None = None,
        evidence: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        status: str = "active",
        applies_to: dict[str, Any] | None = None,
    ) -> Memory:
        return self.create_memory(
            entity_id=entity_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=with_memory_scope(
                applies_to,
                memory_scope=PROJECT_MEMORY_SCOPE,
                project=project,
            ),
        )

    def create_workspace_memory(
        self,
        workspace: str,
        *,
        memory_type: str,
        content: str,
        entity_id: UUID | None = None,
        summary: str | None = None,
        evidence: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        status: str = "active",
        applies_to: dict[str, Any] | None = None,
    ) -> Memory:
        return self.create_memory(
            entity_id=entity_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=with_memory_scope(
                applies_to,
                memory_scope=WORKSPACE_MEMORY_SCOPE,
                workspace=workspace,
            ),
        )

    def create_component_memory(
        self,
        *,
        project: str,
        component: str,
        workspace: str | None = None,
        topic: str | None = None,
        memory_type: str,
        content: str,
        entity_id: UUID | None = None,
        summary: str | None = None,
        evidence: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        status: str = "active",
        applies_to: dict[str, Any] | None = None,
    ) -> Memory:
        return self.create_memory(
            entity_id=entity_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=with_memory_scope(
                applies_to,
                memory_scope=COMPONENT_MEMORY_SCOPE,
                workspace=workspace,
                project=project,
                component=component,
                topic=topic,
            ),
        )

    def update_memory_status(self, memory_id: UUID, status: str) -> Memory:
        return self.memories.update_status(memory_id, status)

    def archive_memory(self, memory_id: UUID) -> Memory:
        return self.memories.archive(memory_id)

    def supersede_memory(
        self,
        old_memory_id: UUID,
        *,
        memory_type: str,
        content: str,
        entity_id: UUID | None = None,
        summary: str | None = None,
        evidence: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        applies_to: dict[str, Any] | None = None,
    ) -> Memory:
        return self.memories.supersede(
            old_memory_id,
            entity_id=entity_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            applies_to=applies_to,
        )

    def tag_memory(
        self,
        memory_id: UUID,
        tag: str,
        *,
        attributes: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        status: str = "active",
        applies_to: dict[str, Any] | None = None,
    ) -> MemoryTag:
        return self.memories.add_tag(
            memory_id,
            tag,
            attributes=attributes,
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=applies_to,
        )

    def create_relationship(
        self,
        *,
        source_entity_id: UUID,
        target_entity_id: UUID,
        relationship_type: str,
        description: str | None = None,
        evidence: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        status: str = "active",
        applies_to: dict[str, Any] | None = None,
    ) -> Relationship:
        return self.relationships.create(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            description=description,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=applies_to,
        )

    def archive_relationship(self, relationship_id: UUID) -> Relationship:
        return self.relationships.archive(relationship_id)

    def list_entities(
        self,
        *,
        entity_type: str | None = None,
        status: str | Sequence[str] | None = None,
        name_contains: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Entity]:
        return self.entities.list(
            entity_type=entity_type,
            status=status,
            name_contains=name_contains,
            limit=limit,
            offset=offset,
        )

    def list_memories(
        self,
        *,
        entity_id: UUID | None = None,
        memory_type: str | None = None,
        status: str | Sequence[str] | None = None,
        sensitivity: str | Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Memory]:
        return self.memories.list(
            entity_id=entity_id,
            memory_type=memory_type,
            status=status,
            sensitivity=sensitivity,
            tags=tags,
            limit=limit,
            offset=offset,
        )

    def list_relationships(
        self,
        *,
        source_entity_id: UUID | None = None,
        target_entity_id: UUID | None = None,
        relationship_type: str | None = None,
        status: str | Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Relationship]:
        return self.relationships.list(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            status=status,
            limit=limit,
            offset=offset,
        )
