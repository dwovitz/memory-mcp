"""Tests that repo is wired through retrieval filters."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from memory_mcp.models import Memory
from memory_mcp.retrieval import HybridRetrievalService, MemorySearchResult
from memory_mcp.retrieval.service import _hierarchy_layers, _layer_applies_to
from memory_mcp.scopes import (
    COMPONENT_MEMORY_SCOPE,
    GLOBAL_MEMORY_SCOPE,
    PROJECT_MEMORY_SCOPE,
    REPO_KEY,
    WORKSPACE_MEMORY_SCOPE,
)
from memory_mcp.services import ContextSynthesisService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSession:
    def __init__(self) -> None:
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        return _EmptyResult()


class _EmptyResult:
    def all(self):
        return []


def compile_sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def _memory(
    *,
    memory_type: str = "project_fact",
    summary: str = "A fact.",
    content: str = "A fact.",
    applies_to: dict | None = None,
) -> Memory:
    return Memory(
        id=uuid4(),
        memory_type=memory_type,
        summary=summary,
        content=content,
        applies_to=applies_to or {},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _result(memory: Memory) -> MemorySearchResult:
    return MemorySearchResult(memory=memory, rank_score=1.0, text_rank=0.5, recency_score=0.5)


# ---------------------------------------------------------------------------
# _hierarchy_layers
# ---------------------------------------------------------------------------


def test_hierarchy_layers_includes_repo_in_project_and_component_layers() -> None:
    layers = _hierarchy_layers(
        workspace="corp",
        repo="my-repo",
        project="my-project",
        component=None,
        topic=None,
        include_global=False,
    )
    # Should produce: component-scope (for project-only case), project-scope, workspace-scope
    project_layers = [lay for lay in layers if lay.get("memory_scope") == PROJECT_MEMORY_SCOPE]
    assert project_layers, "expected a project-scoped layer"
    assert project_layers[0].get("repo") == "my-repo"


def test_hierarchy_layers_repo_in_component_layer() -> None:
    layers = _hierarchy_layers(
        workspace="corp",
        repo="my-repo",
        project="my-project",
        component="auth",
        topic=None,
        include_global=False,
    )
    component_layers = [lay for lay in layers if lay.get("memory_scope") == COMPONENT_MEMORY_SCOPE]
    assert component_layers
    assert component_layers[0].get("repo") == "my-repo"


def test_hierarchy_layers_no_repo_omitted_from_workspace_and_global() -> None:
    layers = _hierarchy_layers(
        workspace="corp",
        repo="my-repo",
        project="my-project",
        component=None,
        topic=None,
        include_global=True,
    )
    workspace_layers = [lay for lay in layers if lay.get("memory_scope") == WORKSPACE_MEMORY_SCOPE]
    global_layers = [lay for lay in layers if lay.get("memory_scope") == GLOBAL_MEMORY_SCOPE]
    assert workspace_layers
    assert "repo" not in workspace_layers[0]
    assert global_layers
    assert "repo" not in global_layers[0]


def test_hierarchy_layers_without_repo_produces_no_repo_key() -> None:
    layers = _hierarchy_layers(
        workspace="corp",
        repo=None,
        project="my-project",
        component=None,
        topic=None,
        include_global=False,
    )
    for layer in layers:
        assert "repo" not in layer


# ---------------------------------------------------------------------------
# _layer_applies_to
# ---------------------------------------------------------------------------


def test_layer_applies_to_injects_repo_for_project_scope() -> None:
    result = _layer_applies_to(
        applies_to=None,
        memory_scope=PROJECT_MEMORY_SCOPE,
        workspace="corp",
        repo="my-repo",
        project="my-project",
    )
    assert result.get(REPO_KEY) == "my-repo"
    assert result.get("memory_scope") == PROJECT_MEMORY_SCOPE


def test_layer_applies_to_strips_repo_for_global_scope() -> None:
    result = _layer_applies_to(
        applies_to={"repo": "my-repo", "project": "my-project"},
        memory_scope=GLOBAL_MEMORY_SCOPE,
    )
    assert REPO_KEY not in result
    assert result.get("memory_scope") == GLOBAL_MEMORY_SCOPE


# ---------------------------------------------------------------------------
# HybridRetrievalService.search_hierarchical_memories
# ---------------------------------------------------------------------------


def test_search_hierarchical_memories_passes_repo_to_each_layer(monkeypatch) -> None:
    """search_hierarchical_memories should inject repo into the applies_to for project layers."""
    service = HybridRetrievalService(FakeSession())
    captured_applies_to: list[dict] = []

    def fake_search_memories(**kwargs):
        captured_applies_to.append(kwargs.get("applies_to") or {})
        return []

    monkeypatch.setattr(service, "search_memories", fake_search_memories)

    service.search_hierarchical_memories(
        workspace="corp",
        repo="repo-a",
        project="proj",
        component=None,
        topic=None,
        include_global=False,
    )

    # At least one call should have repo=repo-a in applies_to
    assert any(at.get(REPO_KEY) == "repo-a" for at in captured_applies_to), (
        f"Expected repo='repo-a' in at least one applies_to, got: {captured_applies_to}"
    )


def test_search_hierarchical_memories_no_repo_does_not_inject_repo(monkeypatch) -> None:
    service = HybridRetrievalService(FakeSession())
    captured_applies_to: list[dict] = []

    def fake_search_memories(**kwargs):
        captured_applies_to.append(kwargs.get("applies_to") or {})
        return []

    monkeypatch.setattr(service, "search_memories", fake_search_memories)

    service.search_hierarchical_memories(
        workspace="corp",
        repo=None,
        project="proj",
        component=None,
        topic=None,
        include_global=False,
    )

    for at in captured_applies_to:
        assert REPO_KEY not in at


# ---------------------------------------------------------------------------
# Repo isolation: repo=A memories are not returned when searching repo=B
# ---------------------------------------------------------------------------


def test_repo_a_memories_excluded_from_repo_b_search(monkeypatch) -> None:
    """Memories scoped to repo-a must not appear when searching with repo=repo-b.

    The fake_search_memories simulates the PostgreSQL JSONB containment filter:
    it only returns memories whose applies_to JSONB contains every key/value
    from the filter dict passed as applies_to.  This is what the real SQL
    ``Memory.applies_to.contains(applies_to)`` does.
    """
    memory_a = _memory(
        summary="Repo A fact.",
        content="This belongs to repo-a.",
        applies_to={
            "memory_scope": PROJECT_MEMORY_SCOPE,
            "workspace": "corp",
            "project": "proj",
            "repo": "repo-a",
        },
    )
    memory_b = _memory(
        summary="Repo B fact.",
        content="This belongs to repo-b.",
        applies_to={
            "memory_scope": PROJECT_MEMORY_SCOPE,
            "workspace": "corp",
            "project": "proj",
            "repo": "repo-b",
        },
    )

    service = HybridRetrievalService(FakeSession())

    def fake_search_memories(**kwargs):
        """Simulate JSONB containment: memory returned only if applies_to filter is a subset."""
        filter_at = kwargs.get("applies_to") or {}
        candidates = [memory_a, memory_b]
        matching = []
        for mem in candidates:
            mem_at = mem.applies_to or {}
            # JSONB @> check: every key in filter must match memory's applies_to
            if all(mem_at.get(k) == v for k, v in filter_at.items()):
                matching.append(_result(mem))
        return matching

    monkeypatch.setattr(service, "search_memories", fake_search_memories)

    results_b = service.search_hierarchical_memories(
        workspace="corp",
        repo="repo-b",
        project="proj",
        include_global=False,
    )
    returned_ids = {r.memory.id for r in results_b}
    assert memory_b.id in returned_ids, "repo-b memory should be returned"
    assert memory_a.id not in returned_ids, "repo-a memory should be excluded when searching repo-b"


def test_search_without_repo_returns_both_repo_memories(monkeypatch) -> None:
    """Searching without repo should return memories from any repo (broader search)."""
    memory_a = _memory(
        summary="Repo A fact.",
        content="Repo A fact.",
        applies_to={
            "memory_scope": PROJECT_MEMORY_SCOPE,
            "workspace": "corp",
            "project": "proj",
            "repo": "repo-a",
        },
    )
    memory_b = _memory(
        summary="Repo B fact.",
        content="Repo B fact.",
        applies_to={
            "memory_scope": PROJECT_MEMORY_SCOPE,
            "workspace": "corp",
            "project": "proj",
            "repo": "repo-b",
        },
    )

    service = HybridRetrievalService(FakeSession())

    def fake_search_memories(**kwargs):
        """Simulate JSONB containment without repo key — returns both memories."""
        filter_at = kwargs.get("applies_to") or {}
        candidates = [memory_a, memory_b]
        matching = []
        for mem in candidates:
            mem_at = mem.applies_to or {}
            if all(mem_at.get(k) == v for k, v in filter_at.items()):
                matching.append(_result(mem))
        return matching

    monkeypatch.setattr(service, "search_memories", fake_search_memories)

    results = service.search_hierarchical_memories(
        workspace="corp",
        repo=None,
        project="proj",
        include_global=False,
    )
    returned_ids = {r.memory.id for r in results}
    assert memory_a.id in returned_ids
    assert memory_b.id in returned_ids


# ---------------------------------------------------------------------------
# ContextSynthesisService.synthesize_context passes repo through
# ---------------------------------------------------------------------------


class FakeRepoAwareRetriever:
    """Retriever that records kwargs and can simulate repo filtering."""

    def __init__(self) -> None:
        self.hierarchical_calls: list[dict] = []

    def search_memories(self, **kwargs) -> list:
        return []

    def search_hierarchical_memories(self, **kwargs) -> list:
        self.hierarchical_calls.append(kwargs)
        return []


def test_synthesize_context_passes_repo_to_hierarchical_search() -> None:
    retriever = FakeRepoAwareRetriever()
    service = ContextSynthesisService(retriever=retriever)

    service.synthesize_context(
        "project architecture",
        workspace="corp",
        repo="my-repo",
        project="my-project",
        max_memories=5,
    )

    assert retriever.hierarchical_calls, "expected search_hierarchical_memories to be called"
    call = retriever.hierarchical_calls[0]
    assert call.get("repo") == "my-repo", (
        f"Expected repo='my-repo' to be passed, got: {call}"
    )
