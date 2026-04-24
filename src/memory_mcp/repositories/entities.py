"""Repository operations for entities."""

from __future__ import annotations

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
        aliases: list[Any] | None = None,
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

    def _require(self, entity_id: UUID) -> Entity:
        entity = self.get(entity_id)
        if entity is None:
            raise LookupError(f"Entity not found: {entity_id}")
        return entity


def _where_status(statement: Select[Any], column: Any, status: str | Sequence[str]) -> Select[Any]:
    if isinstance(status, str):
        return statement.where(column == status)
    return statement.where(column.in_(list(status)))
