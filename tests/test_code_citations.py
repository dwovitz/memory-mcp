"""Tests for P1 code_citations column and QW3 cited_path filter."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import memory_mcp.mcp_tools.server as server_module
from memory_mcp.mcp_tools.server import (
    MUTATION_TOOLS_ENV,
    _validate_code_citations,
)
from memory_mcp.models import Memory


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

def _fake_memory(code_citations=None):
    mem = Memory(
        id=uuid4(),
        memory_type="project_fact",
        content="RoutingService determines reviewer by specialty.",
    )
    if code_citations is not None:
        mem.code_citations = code_citations
    return mem


class _FakeScope:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


# ---------------------------------------------------------------------------
# Unit tests — validator
# ---------------------------------------------------------------------------

def test_citations_rejected_when_too_many():
    with pytest.raises(ValueError, match="code_citations"):
        _validate_code_citations(
            [{"repo": "r", "path": f"file{i}.py", "kind": "file"} for i in range(21)]
        )


def test_citations_rejected_for_absolute_path():
    with pytest.raises(ValueError, match="absolute"):
        _validate_code_citations([{"repo": "r", "path": "/etc/passwd", "kind": "file"}])


def test_citations_rejected_for_windows_absolute_path():
    with pytest.raises(ValueError, match="absolute"):
        _validate_code_citations([{"repo": "r", "path": "C:\\windows\\file.py", "kind": "file"}])


def test_citations_accepted_for_relative_path():
    result = _validate_code_citations(
        [{"repo": "UCX", "path": "Application/Services/RoutingService.cs", "kind": "file"}]
    )
    assert len(result) == 1
    assert result[0]["path"] == "Application/Services/RoutingService.cs"


def test_citations_rejected_for_invalid_kind():
    with pytest.raises(ValueError, match="kind"):
        _validate_code_citations([{"repo": "r", "path": "a/b.py", "kind": "unknown"}])


# ---------------------------------------------------------------------------
# Integration tests — add_memory stores code_citations
# ---------------------------------------------------------------------------

def test_add_memory_with_citations(monkeypatch):
    monkeypatch.setenv(MUTATION_TOOLS_ENV, "true")
    stored = _fake_memory()

    class FakeService:
        def __init__(self, session) -> None:
            pass

        def create_memory(self, **kwargs):
            return stored

        def tag_memory(self, memory_id, tag):
            return SimpleNamespace(id=uuid4(), memory_id=memory_id, tag=tag, status="active")

    monkeypatch.setattr(server_module, "MemoryService", FakeService)
    monkeypatch.setattr(server_module, "session_scope", lambda: _FakeScope())
    monkeypatch.setattr(server_module, "_cache_state_from_session", lambda _: {
        "namespace": "memory-data", "version": "v1", "source_tables": []
    })

    citations = [{"repo": "UCX", "path": "Application/Services/RoutingService.cs", "kind": "file"}]
    result = server_module.add_memory(
        memory_type="project_fact",
        content="RoutingService determines reviewer by specialty.",
        project="UCX.RequestRouting",
        memory_scope="project",
        code_citations=citations,
    )

    assert stored.code_citations == citations
    assert result["memory"]["id"] == str(stored.id)


# ---------------------------------------------------------------------------
# Integration tests — search_memory passes cited_path to retrieval
# ---------------------------------------------------------------------------

def test_search_memory_cited_path_filter(monkeypatch):
    captured = {}

    class FakeRetrieval:
        def __init__(self, session, embedding_service=None) -> None:
            pass

        def search_memories(self, **kwargs):
            captured["cited_path"] = kwargs.get("cited_path")
            return []

    class FakeScope2:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(server_module, "HybridRetrievalService", FakeRetrieval)
    monkeypatch.setattr(server_module, "session_scope", lambda: FakeScope2())
    monkeypatch.setattr(server_module, "get_embedding_service", lambda session: None)
    monkeypatch.setattr(server_module, "_cache_state_from_session", lambda _: {
        "namespace": "memory-data", "version": "v1", "source_tables": []
    })
    monkeypatch.setattr(server_module, "_cache_is_fresh", lambda state, version: False)

    server_module.search_memory(
        query="routing",
        cited_path="Application/Services/RoutingService.cs",
    )

    assert captured.get("cited_path") == "Application/Services/RoutingService.cs"
