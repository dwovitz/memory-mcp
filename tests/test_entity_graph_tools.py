"""Tests for P1 entity graph repository methods and MCP tool logic."""

from __future__ import annotations

from typing import Any
from uuid import uuid4, UUID

import pytest

from memory_mcp.models import Entity, Relationship
from memory_mcp.repositories import EntityRepository, RelationshipRepository


# ---------------------------------------------------------------------------
# FakeSession
# ---------------------------------------------------------------------------

class FakeQuery:
    """Minimal SQLAlchemy query stub that supports filter().first() and filter().all()."""

    def __init__(self, objects: list[Any]) -> None:
        self._objects = objects
        self._filters: list[Any] = []

    def filter(self, *_args: Any) -> "FakeQuery":
        # Real filtering not needed for upsert tests — callers control what's in session
        return FakeQuery(self._objects)

    def first(self) -> Any | None:
        return self._objects[0] if self._objects else None

    def all(self) -> list[Any]:
        return list(self._objects)

    def where(self, *_args: Any) -> "FakeQuery":
        return self


class FakeSession:
    def __init__(self, existing: list[Any] | None = None) -> None:
        self.added: list[Any] = []
        self._existing: list[Any] = existing or []
        self.flush_count = 0

    def add(self, value: Any) -> None:
        self.added.append(value)
        self._existing.append(value)

    def flush(self) -> None:
        self.flush_count += 1

    def get(self, model: type, object_id: Any) -> Any | None:
        for obj in self._existing:
            if isinstance(obj, model) and getattr(obj, "id", None) == object_id:
                return obj
        return None

    def query(self, model: type) -> "FakeQuery":
        return FakeQuery([obj for obj in self._existing if isinstance(obj, model)])

    def scalars(self, _stmt: Any) -> list[Any]:
        return []

    def execute(self, _stmt: Any) -> Any:
        return None


# ---------------------------------------------------------------------------
# EntityRepository.upsert_entity tests
# ---------------------------------------------------------------------------

def test_upsert_entity_creates_new() -> None:
    session = FakeSession()
    repo = EntityRepository(session)
    entity, status = repo.upsert_entity(
        entity_type="service",
        name="UCX.RequestRouting",
        aliases=["request-routing"],
        attributes={"language": ".NET"},
    )
    assert status == "created"
    assert entity.name == "UCX.RequestRouting"
    assert entity.entity_type == "service"
    assert entity in session.added


def test_upsert_entity_is_idempotent() -> None:
    session = FakeSession()
    repo = EntityRepository(session)
    entity1, status1 = repo.upsert_entity(entity_type="service", name="MyService")
    entity2, status2 = repo.upsert_entity(entity_type="service", name="MyService")
    assert status1 == "created"
    assert status2 == "updated"
    assert entity1 is entity2


def test_upsert_entity_updates_aliases_and_attributes() -> None:
    session = FakeSession()
    repo = EntityRepository(session)
    entity, _ = repo.upsert_entity(entity_type="service", name="Svc", aliases=["old"])
    _, status = repo.upsert_entity(
        entity_type="service",
        name="Svc",
        aliases=["new"],
        attributes={"env": "prod"},
    )
    assert status == "updated"
    assert entity.aliases == ["new"]
    assert entity.attributes == {"env": "prod"}


# ---------------------------------------------------------------------------
# RelationshipRepository.link_entities tests
# ---------------------------------------------------------------------------

def test_link_entities_creates_new() -> None:
    session = FakeSession()
    repo = RelationshipRepository(session)
    src_id = uuid4()
    tgt_id = uuid4()
    rel, status = repo.link_entities(
        source_id=src_id,
        target_id=tgt_id,
        relationship_type="produces",
        description="emits events",
    )
    assert status == "created"
    assert rel.source_entity_id == src_id
    assert rel.target_entity_id == tgt_id
    assert rel.relationship_type == "produces"
    assert rel in session.added


def test_link_entities_is_idempotent() -> None:
    session = FakeSession()
    repo = RelationshipRepository(session)
    src_id = uuid4()
    tgt_id = uuid4()
    rel1, status1 = repo.link_entities(source_id=src_id, target_id=tgt_id, relationship_type="calls")
    rel2, status2 = repo.link_entities(source_id=src_id, target_id=tgt_id, relationship_type="calls")
    assert status1 == "created"
    assert status2 == "updated"
    assert rel1 is rel2


# ---------------------------------------------------------------------------
# RelationshipRepository.neighbors tests
# ---------------------------------------------------------------------------

def test_neighbors_returns_list() -> None:
    src_id = uuid4()
    tgt_id = uuid4()
    rel = Relationship(
        source_entity_id=src_id,
        target_entity_id=tgt_id,
        relationship_type="calls",
        status="active",
    )
    session = FakeSession(existing=[rel])
    repo = RelationshipRepository(session)
    results = repo.neighbors(src_id, direction="outbound")
    assert isinstance(results, list)
    assert rel in results


def test_neighbors_inbound_returns_list() -> None:
    src_id = uuid4()
    tgt_id = uuid4()
    rel = Relationship(
        source_entity_id=src_id,
        target_entity_id=tgt_id,
        relationship_type="depends_on",
        status="active",
    )
    session = FakeSession(existing=[rel])
    repo = RelationshipRepository(session)
    results = repo.neighbors(tgt_id, direction="inbound")
    assert isinstance(results, list)
    assert rel in results


def test_neighbors_both_returns_list() -> None:
    a = uuid4()
    b = uuid4()
    rel = Relationship(source_entity_id=a, target_entity_id=b, relationship_type="x", status="active")
    session = FakeSession(existing=[rel])
    repo = RelationshipRepository(session)
    results = repo.neighbors(a, direction="both")
    assert isinstance(results, list)
    assert rel in results
