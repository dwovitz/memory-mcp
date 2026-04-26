"""Basic service layer tests."""

from __future__ import annotations

from uuid import uuid4

from memory_mcp.models import Memory
from memory_mcp.services import MemoryService


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


def test_service_create_entity_and_memory() -> None:
    session = FakeSession()
    service = MemoryService(session)

    entity = service.create_entity(entity_type="project", name="memory-mcp")
    memory = service.create_memory(
        entity_id=uuid4(),
        memory_type="project_fact",
        content="Local-first memory server.",
    )

    assert entity.name == "memory-mcp"
    assert memory.content == "Local-first memory server."
    assert session.added == [entity, memory]
    assert session.flush_count == 2


def test_service_archive_and_supersede_memory() -> None:
    session = FakeSession()
    service = MemoryService(session)
    old_id = uuid4()
    archived_id = uuid4()
    old_memory = Memory(id=old_id, memory_type="preference", content="Old", sensitivity="sensitive")
    archived_memory = Memory(id=archived_id, memory_type="note", content="Archive me")
    session.objects[(Memory, old_id)] = old_memory
    session.objects[(Memory, archived_id)] = archived_memory

    archived = service.archive_memory(archived_id)
    replacement = service.supersede_memory(
        old_id,
        memory_type="preference",
        content="New",
    )

    assert archived.status == "archived"
    assert old_memory.status == "superseded"
    assert replacement.supersedes_memory_id == old_id
    assert replacement.sensitivity == "sensitive"


def test_service_create_scoped_memories() -> None:
    session = FakeSession()
    service = MemoryService(session)

    global_memory = service.create_global_memory(
        memory_type="coding_preference",
        content="Prefer concise status updates.",
        applies_to={"scope": "development"},
    )
    project_memory = service.create_project_memory(
        "memory-mcp",
        memory_type="project_fact",
        content="Uses PostgreSQL for durable memory storage.",
    )
    workspace_memory = service.create_workspace_memory(
        "ai",
        memory_type="project_fact",
        content="Workspace contains sibling repositories.",
    )
    component_memory = service.create_component_memory(
        project="memory-mcp",
        component="retrieval",
        memory_type="project_fact",
        content="Retrieval ranks memory by text and recency.",
    )
    release_memory = service.create_project_memory(
        "memory-mcp",
        memory_type="project_fact",
        content="Release process is documented.",
        applies_to={"scope": "release"},
    )

    assert global_memory.applies_to == {
        "scope": "development",
        "memory_scope": "global",
    }
    assert project_memory.applies_to == {
        "scope": "development",
        "memory_scope": "project",
        "project": "memory-mcp",
    }
    assert workspace_memory.applies_to == {
        "scope": "development",
        "memory_scope": "workspace",
        "workspace": "ai",
    }
    assert component_memory.applies_to == {
        "scope": "development",
        "memory_scope": "component",
        "project": "memory-mcp",
        "component": "retrieval",
    }
    assert release_memory.applies_to == {
        "scope": "release",
        "memory_scope": "project",
        "project": "memory-mcp",
    }
