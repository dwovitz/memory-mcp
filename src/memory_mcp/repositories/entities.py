"""Repository operations for entities."""

from __future__ import annotations

import builtins
from collections.abc import Sequence
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from memory_mcp.models import Entity


class EntityRepository:
    """CRUD and list operations for entity records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        entity_type: str,
        name: str,
        aliases: builtins.list[Any] | None = None,
        attributes: dict[str, Any] | None = None,
        confidence: Decimal | str | float = Decimal("1.0"),
        sensitivity: str = "normal",
        status: str = "active",
        applies_to: dict[str, Any] | None = None,
    ) -> Entity:
        entity = Entity(
            entity_type=entity_type,
            name=name,
            aliases=aliases or [],
            attributes=attributes or {},
            confidence=confidence,
            sensitivity=sensitivity,
            status=status,
            applies_to=applies_to or {},
        )
        self.session.add(entity)
        self.session.flush()
        return entity

    def get(self, entity_id: UUID) -> Entity | None:
        return self.session.get(Entity, entity_id)

    def update_status(self, entity_id: UUID, status: str) -> Entity:
        entity = self._require(entity_id)
        entity.status = status
        return entity

    def archive(self, entity_id: UUID) -> Entity:
        return self.update_status(entity_id, "archived")

    def list(
        self,
        *,
        entity_type: str | None = None,
        status: str | Sequence[str] | None = None,
        name_contains: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Entity]:
        statement = self.build_list_statement(
            entity_type=entity_type,
            status=status,
            name_contains=name_contains,
            limit=limit,
            offset=offset,
        )
        return list(self.session.scalars(statement))

    def build_list_statement(
        self,
        *,
        entity_type: str | None = None,
        status: str | Sequence[str] | None = None,
        name_contains: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Select[tuple[Entity]]:
        statement = select(Entity).order_by(Entity.name).limit(limit).offset(offset)

        if entity_type is not None:
            statement = statement.where(Entity.entity_type == entity_type)
        if status is not None:
            statement = _where_status(statement, Entity.status, status)
        if name_contains is not None:
            statement = statement.where(Entity.name.ilike(f"%{name_contains}%"))

        return statement

    def upsert_entity(
        self,
        entity_type: str,
        name: str,
        aliases: builtins.list[Any] | None = None,
        attributes: dict[str, Any] | None = None,
        applies_to: dict[str, Any] | None = None,
    ) -> tuple["Entity", str]:
        """Return (entity, status) where status is 'created' or 'updated'."""
        existing = self.session.query(Entity).filter(
            Entity.entity_type == entity_type,
            Entity.name == name,
        ).first()
        if existing:
            if aliases is not None:
                existing.aliases = aliases
            if attributes is not None:
                existing.attributes = attributes
            if applies_to is not None:
                existing.applies_to = applies_to
            return existing, "updated"
        entity = Entity(
            entity_type=entity_type,
            name=name,
            aliases=aliases or [],
            attributes=attributes or {},
            applies_to=applies_to or {},
        )
        self.session.add(entity)
        self.session.flush()
        return entity, "created"

    def find_active_by_attribute(self, field: str, value: str) -> Entity | None:
        """Return the first active entity whose ``attributes[field]`` equals ``value``."""
        stmt = (
            select(Entity)
            .where(Entity.status == "active")
            .where(Entity.attributes[field].astext == value)
        )
        return self.session.scalars(stmt).first()

    def list_active_wiki_documents(self, collection: str) -> Sequence[Entity]:
        """List active wiki document entities for a single collection.

        Matches the nested provenance markers written by wiki graph projection
        (``attributes.source.provenance == 'wiki'`` and
        ``attributes.source.collection == collection``) so the stale sweep stays
        scoped to one wiki and never touches other entities.
        """
        stmt = (
            select(Entity)
            .where(Entity.status == "active")
            .where(Entity.entity_type == "wiki_document")
            .where(Entity.attributes["source"]["provenance"].astext == "wiki")
            .where(Entity.attributes["source"]["collection"].astext == collection)
        )
        return list(self.session.scalars(stmt).unique())

    def upsert_provenance(
        self,
        *,
        entity_type: str,
        name: str,
        ingest_key: str,
        attributes: dict[str, Any] | None = None,
        applies_to: dict[str, Any] | None = None,
        sensitivity: str = "normal",
    ) -> tuple["Entity", str]:
        """Idempotently upsert a provenance-stamped entity keyed by ``ingest_key``.

        Identity is the projection ``ingest_key`` stored at
        ``attributes['ingest_key']`` (not ``(entity_type, name)``), so renaming a
        source file updates the same node instead of orphaning it. Returns
        ``(entity, status)`` where status is ``'created'`` or ``'updated'``.
        """
        merged_attributes = dict(attributes or {})
        merged_attributes["ingest_key"] = ingest_key
        existing = self.find_active_by_attribute("ingest_key", ingest_key)
        if existing is not None:
            existing.entity_type = entity_type
            existing.name = name
            existing.attributes = merged_attributes
            if applies_to is not None:
                existing.applies_to = applies_to
            existing.sensitivity = sensitivity
            return existing, "updated"
        entity = self.create(
            entity_type=entity_type,
            name=name,
            attributes=merged_attributes,
            applies_to=applies_to,
            sensitivity=sensitivity,
        )
        return entity, "created"

    def _require(self, entity_id: UUID) -> Entity:
        entity = self.get(entity_id)
        if entity is None:
            raise LookupError(f"Entity not found: {entity_id}")
        return entity


def _where_status(statement: Select[Any], column: Any, status: str | Sequence[str]) -> Select[Any]:
    if isinstance(status, str):
        return statement.where(column == status)
    return statement.where(column.in_(list(status)))
