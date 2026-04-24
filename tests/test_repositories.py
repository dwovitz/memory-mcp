"""Basic repository layer tests."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.dialects import postgresql

from memory_mcp.models import Entity, Memory, MemoryTag, Relationship
from memory_mcp.repositories import EntityRepository, MemoryRepository, RelationshipRepository


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.objects = {}
        self.flush_count = 0

    def add(self, value):
        self.added.append(value)

    def flush(self) -> None:
        self.flush_count += 1

    def get(self, model, object_id):
        return self.objects.get((model, object_id))


def test_entity_repository_create_adds_and_flushes_entity() -> None:
    session = FakeSession()
    repository = EntityRepository(session)

    entity = repository.create(
        entity_type="person",
        name="Alex",
        aliases=["self"],
        attributes={"seed": True},
    )

    assert isinstance(entity, Entity)
    assert entity.entity_type == "person"
    assert entity.name == "Alex"
    assert session.added == [entity]
    assert session.flush_count == 1


def test_memory_repository_archive_updates_status() -> None:
    memory_id = uuid4()
    memory = Memory(id=memory_id, memory_type="preference", content="Likes concise updates.")
    session = FakeSession()
    session.objects[(Memory, memory_id)] = memory
    repository = MemoryRepository(session)

    archived = repository.archive(memory_id)

    assert archived is memory
    assert archived.status == "archived"


def test_memory_repository_supersede_marks_old_and_creates_new() -> None:
    old_id = uuid4()
    entity_id = uuid4()
    old_memory = Memory(
        id=old_id,
        entity_id=entity_id,
        memory_type="coding_preference",
        content="Old preference.",
    )
    session = FakeSession()
    session.objects[(Memory, old_id)] = old_memory
    repository = MemoryRepository(session)

    new_memory = repository.supersede(
        old_id,
        memory_type="coding_preference",
        content="New preference.",
    )

    assert old_memory.status == "superseded"
    assert old_memory.superseded_at is not None
    assert new_memory.supersedes_memory_id == old_id
    assert new_memory.entity_id == entity_id
    assert new_memory.content == "New preference."
    assert session.added == [new_memory]


def test_memory_repository_supersede_preserves_old_applies_to_by_default() -> None:
    old_id = uuid4()
    old_memory = Memory(
        id=old_id,
        memory_type="project_fact",
        content="Old fact.",
        applies_to={"memory_scope": "project", "project": "memory-test"},
    )
    session = FakeSession()
    session.objects[(Memory, old_id)] = old_memory
    repository = MemoryRepository(session)

    new_memory = repository.supersede(
        old_id,
        memory_type="project_fact",
        content="New fact.",
    )

    assert new_memory.applies_to == {"memory_scope": "project", "project": "memory-test"}


def test_memory_repository_add_tag_requires_memory_and_flushes() -> None:
    memory_id = uuid4()
    memory = Memory(id=memory_id, memory_type="project_fact", content="Uses PostgreSQL.")
    session = FakeSession()
    session.objects[(Memory, memory_id)] = memory
    repository = MemoryRepository(session)

    tag = repository.add_tag(memory_id, "project", attributes={"kind": "seed"})

    assert isinstance(tag, MemoryTag)
    assert tag.memory_id == memory_id
    assert tag.tag == "project"
    assert tag.attributes == {"kind": "seed"}
    assert session.added == [tag]
    assert session.flush_count == 1


def test_relationship_repository_create_adds_relationship() -> None:
    session = FakeSession()
    repository = RelationshipRepository(session)
    source_id = uuid4()
    target_id = uuid4()

    relationship = repository.create(
        source_entity_id=source_id,
        target_entity_id=target_id,
        relationship_type="uses_device",
    )

    assert isinstance(relationship, Relationship)
    assert relationship.source_entity_id == source_id
    assert relationship.target_entity_id == target_id
    assert relationship.relationship_type == "uses_device"
    assert session.added == [relationship]
    assert session.flush_count == 1


def test_memory_list_statement_supports_basic_filters() -> None:
    repository = MemoryRepository(FakeSession())

    statement = repository.build_list_statement(
        memory_type="project_fact",
        status=["active", "archived"],
        sensitivity="normal",
        tags=["project"],
        limit=10,
    )
    compiled = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))

    assert "JOIN memory_tags" in compiled
    assert "memories.memory_type = 'project_fact'" in compiled
    assert "memories.status IN ('active', 'archived')" in compiled
    assert "memories.sensitivity = 'normal'" in compiled
    assert "memory_tags.tag IN ('project')" in compiled
    assert "LIMIT 10" in compiled
