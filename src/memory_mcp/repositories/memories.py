"""Repository operations for memories and tags."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from memory_mcp.models import Memory, MemoryTag


class MemoryRepository:
    """CRUD, lifecycle, tagging, and list operations for memories."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
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
        supersedes_memory_id: UUID | None = None,
    ) -> Memory:
        memory = Memory(
            entity_id=entity_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            evidence=evidence or [],
            metadata_=metadata or {},
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=applies_to or {},
            supersedes_memory_id=supersedes_memory_id,
        )
        self.session.add(memory)
        self.session.flush()
        return memory

    def get(self, memory_id: UUID) -> Memory | None:
        return self.session.get(Memory, memory_id)

    def update_status(self, memory_id: UUID, status: str) -> Memory:
        memory = self._require(memory_id)
        memory.status = status
        if status == "superseded" and memory.superseded_at is None:
            memory.superseded_at = datetime.now(timezone.utc)
        return memory

    def archive(self, memory_id: UUID) -> Memory:
        return self.update_status(memory_id, "archived")

    def supersede(
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
        sensitivity: str | None = None,
        applies_to: dict[str, Any] | None = None,
    ) -> Memory:
        old_memory = self.update_status(old_memory_id, "superseded")
        new_memory = self.create(
            entity_id=entity_id if entity_id is not None else old_memory.entity_id,
            memory_type=memory_type,
            content=content,
            summary=summary,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity if sensitivity is not None else old_memory.sensitivity,
            status="active",
            applies_to=applies_to if applies_to is not None else old_memory.applies_to,
            supersedes_memory_id=old_memory_id,
        )
        return new_memory

    def add_tag(
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
        memory = self._require(memory_id)
        memory_tag = MemoryTag(
            memory_id=memory.id,
            tag=tag,
            attributes=attributes or {},
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=applies_to or {},
        )
        self.session.add(memory_tag)
        self.session.flush()
        return memory_tag

    def list(
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
        statement = self.build_list_statement(
            entity_id=entity_id,
            memory_type=memory_type,
            status=status,
            sensitivity=sensitivity,
            tags=tags,
            limit=limit,
            offset=offset,
        )
        return list(self.session.scalars(statement).unique())

    def build_list_statement(
        self,
        *,
        entity_id: UUID | None = None,
        memory_type: str | None = None,
        status: str | Sequence[str] | None = None,
        sensitivity: str | Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Select[tuple[Memory]]:
        statement = select(Memory).order_by(Memory.created_at.desc()).limit(limit).offset(offset)

        if tags:
            statement = statement.join(MemoryTag, MemoryTag.memory_id == Memory.id).where(MemoryTag.tag.in_(list(tags)))
        if entity_id is not None:
            statement = statement.where(Memory.entity_id == entity_id)
        if memory_type is not None:
            statement = statement.where(Memory.memory_type == memory_type)
        if status is not None:
            statement = _where_value(statement, Memory.status, status)
        if sensitivity is not None:
            statement = _where_value(statement, Memory.sensitivity, sensitivity)

        return statement

    def find_active_by_metadata_key(self, field: str, value: str) -> Memory | None:
        """Find the first active memory whose metadata JSONB contains the given field/value pair."""
        stmt = (
            select(Memory)
            .where(Memory.status == "active")
            .where(Memory.metadata_[field].astext == value)
        )
        return self.session.scalars(stmt).first()

    def _require(self, memory_id: UUID) -> Memory:
        memory = self.get(memory_id)
        if memory is None:
            raise LookupError(f"Memory not found: {memory_id}")
        return memory


def _where_value(statement: Select[Any], column: Any, value: str | Sequence[str]) -> Select[Any]:
    if isinstance(value, str):
        return statement.where(column == value)
    return statement.where(column.in_(list(value)))
