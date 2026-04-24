"""Hybrid retrieval service tests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from memory_mcp.models import Memory
from memory_mcp.retrieval import HybridRetrievalService
from memory_mcp.retrieval.service import MemorySearchResult


class EmptyResult:
    def all(self):
        return []


class FakeSession:
    def __init__(self) -> None:
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return EmptyResult()


def compile_sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_search_memories_statement_combines_text_tags_confidence_and_scope() -> None:
    service = HybridRetrievalService(FakeSession())

    statement = service.build_search_memories_statement(
        text_query="postgres memory",
        memory_types=("project_fact",),
        tags=("project",),
        scope="development",
        applies_to={"project": "memory-mcp"},
        min_confidence="0.75",
        limit=5,
    )
    sql = compile_sql(statement)

    assert "JOIN memory_tags" in sql
    assert "to_tsvector" in sql
    assert "to_tsquery" in sql
    assert "@@" in sql
    assert "memories.memory_type IN" in sql
    assert "memory_tags.tag IN" in sql
    assert "memories.confidence >=" in sql
    assert "memories.applies_to" in sql
    assert "ORDER BY rank_score DESC" in sql


def test_search_memories_statement_matches_exact_scope_path() -> None:
    service = HybridRetrievalService(FakeSession())

    statement = service.build_search_memories_statement(
        text_query="attack buffering",
        scope_path=("global", "user:David", "project:Game", "branch:combat-refactor"),
        limit=5,
    )
    sql = compile_sql(statement)

    assert "memories.applies_to[" in sql
    assert "CAST" in sql
    assert "scope_path" not in sql


def test_search_memories_rejects_vector_query_until_pipeline_exists() -> None:
    service = HybridRetrievalService(FakeSession())

    with pytest.raises(NotImplementedError, match="Vector search is scaffolded only"):
        service.search_memories(query_embedding=[0.1, 0.2, 0.3])


def test_search_entities_statement_filters_type_status_scope_and_confidence() -> None:
    service = HybridRetrievalService(FakeSession())

    statement = service.build_search_entities_statement(
        text_query="codex",
        entity_types=("app", "project"),
        scope="development",
        min_confidence="0.8",
    )
    sql = compile_sql(statement)

    assert "lower(entities.name)" in sql
    assert "entities.entity_type IN" in sql
    assert "entities.status IN" in sql
    assert "entities.applies_to" in sql
    assert "entities.confidence >=" in sql


def test_entertainment_by_genre_statement_uses_relationship_graph_and_tag() -> None:
    service = HybridRetrievalService(FakeSession())

    statement = service.build_entertainment_items_by_genre_statement(
        "Science fiction",
        liked=True,
        person_id=uuid4(),
    )
    sql = compile_sql(statement)

    assert "JOIN memory_tags" in sql
    assert "JOIN entities AS" in sql
    assert "JOIN relationships" in sql
    assert "relationships.relationship_type" in sql
    assert "has_genre" in sql or "relationship_type_1" in sql
    assert "memory_tags.tag" in sql
    assert "memories.applies_to" in sql


def test_profile_helpers_delegate_to_search_memories(monkeypatch) -> None:
    service = HybridRetrievalService(FakeSession())
    calls = []

    def fake_search_memories(**kwargs):
        calls.append(kwargs)
        return []

    monkeypatch.setattr(service, "search_memories", fake_search_memories)
    person_id = uuid4()

    assert service.get_medications_for_person(person_id) == []
    assert service.get_entertainment_profile(person_id) == {
        "liked": [],
        "disliked": [],
        "inferred": [],
    }
    assert service.get_project_context("memory-mcp") == []

    assert any(call.get("memory_types") == ("medication",) for call in calls)
    assert any(call.get("tags") == ("liked",) for call in calls)
    assert any(call.get("tags") == ("disliked",) for call in calls)
    assert any(
        call.get("applies_to") == {
            "memory_scope": "project",
            "project": "memory-mcp",
        }
        for call in calls
    )


def test_vector_search_plan_is_scaffold_only() -> None:
    service = HybridRetrievalService(FakeSession())

    plan = service.vector_search_plan(embedding_dimensions=1536)

    assert plan.status == "scaffold_only"
    assert plan.embedding_dimensions == 1536
    assert plan.preferred_index == "hnsw"
    assert plan.distance_metric == "cosine"


def test_search_hierarchical_memories_merges_scopes_with_priority_and_caps(monkeypatch) -> None:
    service = HybridRetrievalService(FakeSession())
    calls = []
    component_memory = Memory(
        id=uuid4(),
        memory_type="project_fact",
        content="Component-specific auth rule.",
        summary="Component-specific auth rule.",
        applies_to={
            "memory_scope": "component",
            "workspace": "corp-root",
            "project": "memory-mcp",
            "component": "auth",
        },
        created_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
    )
    project_memory = Memory(
        id=uuid4(),
        memory_type="project_fact",
        content="Project-specific rule.",
        summary="Project-specific rule.",
        applies_to={"memory_scope": "project", "project": "memory-mcp"},
        created_at=datetime(2026, 4, 23, tzinfo=timezone.utc),
    )
    global_memory = Memory(
        id=uuid4(),
        memory_type="coding_preference",
        content="Global rule.",
        summary="Global rule.",
        applies_to={"memory_scope": "global"},
        created_at=datetime(2026, 4, 23, tzinfo=timezone.utc),
    )

    def fake_search_memories(**kwargs):
        calls.append(kwargs)
        applies_to = kwargs.get("applies_to") or {}
        if applies_to.get("memory_scope") == "component":
            return [MemorySearchResult(component_memory, 0.2, 0.0, 0.1)]
        if applies_to.get("memory_scope") == "project":
            return [MemorySearchResult(project_memory, 0.1, 0.0, 0.1)]
        return [MemorySearchResult(global_memory, 9.0, 0.0, 0.1)]

    monkeypatch.setattr(service, "search_memories", fake_search_memories)

    results = service.search_hierarchical_memories(
        workspace="corp-root",
        project="memory-mcp",
        component="auth",
        text_query="security rules",
        applies_to={"scope": "development"},
        limit=5,
    )

    assert [result.memory.id for result in results] == [
        component_memory.id,
        project_memory.id,
        global_memory.id,
    ]
    assert calls[0]["applies_to"] == {
        "scope": "development",
        "memory_scope": "component",
        "workspace": "corp-root",
        "project": "memory-mcp",
        "component": "auth",
    }
    assert calls[1]["applies_to"] == {
        "scope": "development",
        "memory_scope": "project",
        "workspace": "corp-root",
        "project": "memory-mcp",
    }
    assert calls[2]["applies_to"] == {
        "scope": "development",
        "memory_scope": "workspace",
        "workspace": "corp-root",
    }
    assert calls[3]["applies_to"] == {
        "scope": "development",
        "memory_scope": "global",
    }


def test_scope_path_search_inherits_parents_and_applies_lower_scope_overrides(monkeypatch) -> None:
    service = HybridRetrievalService(FakeSession())
    calls = []
    main_memory = Memory(
        id=uuid4(),
        memory_type="architecture_decision",
        content="PlayerAttack polls Input.GetButtonDown.",
        summary="Old main input decision.",
        applies_to={"scope_path": ["global", "project:Metroidvania", "module:combat"]},
        created_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )
    branch_memory = Memory(
        id=uuid4(),
        memory_type="architecture_decision",
        content="combat-refactor uses event-driven input.",
        summary="Branch input decision.",
        applies_to={
            "scope_path": [
                "global",
                "project:Metroidvania",
                "module:combat",
                "branch:combat-refactor",
            ],
        },
        metadata_={"overrides_memory_ids": [str(main_memory.id)]},
        created_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
    )
    project_memory = Memory(
        id=uuid4(),
        memory_type="project_rule",
        content="Preserve controller support.",
        summary="Preserve controller support.",
        applies_to={"scope_path": ["global", "project:Metroidvania"]},
        created_at=datetime(2026, 4, 19, tzinfo=timezone.utc),
    )

    def fake_search_memories(**kwargs):
        calls.append(kwargs)
        scope_path = list(kwargs["scope_path"])
        if scope_path[-1] == "branch:combat-refactor":
            return [MemorySearchResult(branch_memory, 0.4, 0.0, 0.1)]
        if scope_path[-1] == "module:combat":
            return [MemorySearchResult(main_memory, 9.0, 0.0, 0.1)]
        if scope_path[-1] == "project:Metroidvania":
            return [MemorySearchResult(project_memory, 0.2, 0.0, 0.1)]
        return []

    monkeypatch.setattr(service, "search_memories", fake_search_memories)

    results = service.search_scope_path_memories(
        scope_path=[
            "global",
            "project:Metroidvania",
            "module:combat",
            "branch:combat-refactor",
        ],
        memory_types=("architecture_decision", "project_rule"),
        limit=5,
    )

    assert [result.memory.id for result in results] == [branch_memory.id, project_memory.id]
    assert [call["scope_path"] for call in calls] == [
        ("global", "project:Metroidvania", "module:combat", "branch:combat-refactor"),
        ("global", "project:Metroidvania", "module:combat"),
        ("global", "project:Metroidvania"),
        ("global",),
    ]


def test_scope_path_search_excludes_memories_outside_validity_window(monkeypatch) -> None:
    service = HybridRetrievalService(FakeSession())
    expired = Memory(
        id=uuid4(),
        memory_type="branch_note",
        content="Expired branch note.",
        summary="Expired branch note.",
        applies_to={
            "scope_path": ["global", "project:Game", "branch:old"],
            "valid_to": "2026-04-01T00:00:00+00:00",
        },
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    monkeypatch.setattr(
        service,
        "search_memories",
        lambda **_: [MemorySearchResult(expired, 1.0, 0.0, 0.1)],
    )

    results = service.search_scope_path_memories(
        scope_path=["global", "project:Game", "branch:old"],
        include_inherited=False,
        valid_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
    )

    assert results == []
