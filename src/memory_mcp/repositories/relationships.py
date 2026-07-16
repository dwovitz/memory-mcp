"""Repository operations for entity relationships."""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from memory_mcp.models import Relationship


class RelationshipRepository:
    """CRUD, lifecycle, and list operations for relationships."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
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
        supersedes_relationship_id: UUID | None = None,
    ) -> Relationship:
        relationship = Relationship(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            description=description,
            evidence=evidence or [],
            metadata_=metadata or {},
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=applies_to or {},
            supersedes_relationship_id=supersedes_relationship_id,
        )
        self.session.add(relationship)
        self.session.flush()
        return relationship

    def get(self, relationship_id: UUID) -> Relationship | None:
        return self.session.get(Relationship, relationship_id)

    def update_status(self, relationship_id: UUID, status: str) -> Relationship:
        relationship = self._require(relationship_id)
        relationship.status = status
        return relationship

    def archive(self, relationship_id: UUID) -> Relationship:
        return self.update_status(relationship_id, "archived")

    def supersede(
        self,
        old_relationship_id: UUID,
        *,
        source_entity_id: UUID,
        target_entity_id: UUID,
        relationship_type: str,
        description: str | None = None,
        evidence: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        applies_to: dict[str, Any] | None = None,
    ) -> Relationship:
        self.update_status(old_relationship_id, "superseded")
        return self.create(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            description=description,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            status="active",
            applies_to=applies_to,
            supersedes_relationship_id=old_relationship_id,
        )

    def list(
        self,
        *,
        source_entity_id: UUID | None = None,
        target_entity_id: UUID | None = None,
        relationship_type: str | None = None,
        status: str | Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> builtins.list[Relationship]:
        statement = self.build_list_statement(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            status=status,
            limit=limit,
            offset=offset,
        )
        return list(self.session.scalars(statement))

    def build_list_statement(
        self,
        *,
        source_entity_id: UUID | None = None,
        target_entity_id: UUID | None = None,
        relationship_type: str | None = None,
        status: str | Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Select[tuple[Relationship]]:
        statement = select(Relationship).order_by(Relationship.created_at.desc()).limit(limit).offset(offset)

        if source_entity_id is not None:
            statement = statement.where(Relationship.source_entity_id == source_entity_id)
        if target_entity_id is not None:
            statement = statement.where(Relationship.target_entity_id == target_entity_id)
        if relationship_type is not None:
            statement = statement.where(Relationship.relationship_type == relationship_type)
        if status is not None:
            statement = _where_status(statement, Relationship.status, status)

        return statement

    def link_entities(
        self,
        source_id: UUID,
        target_id: UUID,
        relationship_type: str,
        description: str | None = None,
        evidence: builtins.list[Any] | None = None,
        applies_to: dict[str, Any] | None = None,
    ) -> tuple["Relationship", str]:
        """Return (relationship, status) where status is 'created' or 'updated'."""
        existing = self.session.query(Relationship).filter(
            Relationship.source_entity_id == source_id,
            Relationship.target_entity_id == target_id,
            Relationship.relationship_type == relationship_type,
        ).first()
        if existing:
            if description is not None:
                existing.description = description
            return existing, "updated"
        rel = Relationship(
            source_entity_id=source_id,
            target_entity_id=target_id,
            relationship_type=relationship_type,
            description=description,
            evidence=evidence or [],
            applies_to=applies_to or {},
        )
        self.session.add(rel)
        self.session.flush()
        return rel, "created"

    def neighbors(
        self,
        entity_id: UUID,
        relationship_types: tuple[str, ...] | None = None,
        direction: str = "both",
    ) -> builtins.list["Relationship"]:
        """Return relationships where entity_id is source, target, or either."""
        q = self.session.query(Relationship).filter(Relationship.status == "active")
        if direction == "outbound":
            q = q.filter(Relationship.source_entity_id == entity_id)
        elif direction == "inbound":
            q = q.filter(Relationship.target_entity_id == entity_id)
        else:
            from sqlalchemy import or_
            q = q.filter(
                or_(
                    Relationship.source_entity_id == entity_id,
                    Relationship.target_entity_id == entity_id,
                )
            )
        if relationship_types:
            q = q.filter(Relationship.relationship_type.in_(relationship_types))
        return q.all()

    def find_active_by_metadata(self, field: str, value: str) -> Relationship | None:
        """Return the first active relationship whose ``metadata[field]`` equals ``value``."""
        stmt = (
            select(Relationship)
            .where(Relationship.status == "active")
            .where(Relationship.metadata_[field].astext == value)
        )
        return self.session.scalars(stmt).first()

    def list_active_wiki_references(self, collection: str) -> Sequence[Relationship]:
        """List active wiki ``references`` edges for a single collection.

        Matches the nested provenance markers written by wiki graph projection
        (``metadata.source.provenance == 'wiki'`` and
        ``metadata.source.collection == collection``) so the stale sweep stays
        scoped to one wiki and never touches other relationships.
        """
        stmt = (
            select(Relationship)
            .where(Relationship.status == "active")
            .where(Relationship.relationship_type == "references")
            .where(Relationship.metadata_["source"]["provenance"].astext == "wiki")
            .where(Relationship.metadata_["source"]["collection"].astext == collection)
        )
        return list(self.session.scalars(stmt).unique())

    def upsert_provenance(
        self,
        *,
        source_entity_id: UUID,
        target_entity_id: UUID,
        relationship_type: str,
        ref_key: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        applies_to: dict[str, Any] | None = None,
        sensitivity: str = "normal",
    ) -> tuple["Relationship", str]:
        """Idempotently upsert a provenance-stamped relationship keyed by ``ref_key``.

        Identity is the projection ``ref_key`` stored at ``metadata['ref_key']``,
        so re-deriving an unchanged edge updates the same row. Returns
        ``(relationship, status)`` where status is ``'created'`` or ``'updated'``.
        """
        merged_metadata = dict(metadata or {})
        merged_metadata["ref_key"] = ref_key
        existing = self.find_active_by_metadata("ref_key", ref_key)
        if existing is not None:
            existing.source_entity_id = source_entity_id
            existing.target_entity_id = target_entity_id
            existing.relationship_type = relationship_type
            if description is not None:
                existing.description = description
            existing.metadata_ = merged_metadata
            if applies_to is not None:
                existing.applies_to = applies_to
            existing.sensitivity = sensitivity
            return existing, "updated"
        relationship = self.create(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relationship_type=relationship_type,
            description=description,
            metadata=merged_metadata,
            applies_to=applies_to,
            sensitivity=sensitivity,
        )
        return relationship, "created"

    def _require(self, relationship_id: UUID) -> Relationship:
        relationship = self.get(relationship_id)
        if relationship is None:
            raise LookupError(f"Relationship not found: {relationship_id}")
        return relationship


def _where_status(statement: Select[Any], column: Any, status: str | Sequence[str]) -> Select[Any]:
    if isinstance(status, str):
        return statement.where(column == status)
    return statement.where(column.in_(list(status)))
