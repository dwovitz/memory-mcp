"""Tests for ProjectionRetrievalService: combined retrieval, bounded expansion,
sensitivity filtering, token budget, exact lookup, and why-retrieved reasons.

All fakes are in-memory so behavior is validated without a database.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from memory_mcp.retrieval.projection import (
    REASON_EXACT_LOOKUP,
    REASON_PRIMARY_MATCH,
    REASON_RELATIONSHIP_EXPANSION,
    ProjectionRetrievalService,
)


class _FakeMemory:
    def __init__(self, content, *, entity_id=None, sensitivity="normal", source=None, primary=False):
        self.id = uuid4()
        self.content = content
        self.entity_id = entity_id
        self.sensitivity = sensitivity
        self.metadata_ = {"source": source} if source else {}
        self.confidence = 0.9
        self.primary = primary


class _FakeResult:
    def __init__(self, memory, rank_score=1.0):
        self.memory = memory
        self.rank_score = rank_score


class _FakeRetriever:
    """Returns `primary` memories for text search and entity-scoped memories for expansion."""

    def __init__(self, memories: list[_FakeMemory]) -> None:
        self.memories = memories

    def search_memories(self, **kwargs: Any) -> list[_FakeResult]:
        entity_id = kwargs.get("entity_id")
        sens = kwargs.get("sensitivities")
        allowed = set(sens) if sens is not None else None
        limit = kwargs.get("limit", 10)
        out = []
        for m in self.memories:
            if allowed is not None and m.sensitivity not in allowed:
                continue
            if entity_id is not None:
                if m.entity_id != entity_id:
                    continue
            else:
                if not m.primary:
                    continue
            out.append(_FakeResult(m, rank_score=2.0 if m.primary else 1.0))
        return out[:limit]


class _FakeRel:
    def __init__(self, source_id, target_id, rel_type="references", sensitivity="normal"):
        self.source_entity_id = source_id
        self.target_entity_id = target_id
        self.relationship_type = rel_type
        self.sensitivity = sensitivity
        self.description = None


class _FakeNeighborSource:
    def __init__(self, rels: list[_FakeRel]) -> None:
        self.rels = rels

    def neighbors(self, entity_id, relationship_types=None, direction="both"):
        out = []
        for r in self.rels:
            if r.source_entity_id == entity_id or r.target_entity_id == entity_id:
                if relationship_types and r.relationship_type not in relationship_types:
                    continue
                out.append(r)
        return out


class _FakeMemoryLookup:
    def __init__(self, memories: list[_FakeMemory]) -> None:
        self.memories = memories

    def find_active_by_metadata_key(self, field, value):
        for m in self.memories:
            if (m.metadata_ or {}).get(field) == value:
                return m
        return None

    def find_active_wiki_by_source(self, *, collection, path, section=None):
        for m in self.memories:
            src = (m.metadata_ or {}).get("source", {})
            if src.get("collection") == collection and src.get("path") == path:
                if section is None or src.get("section") == section:
                    return m
        return None


def _service(memories, rels=None, lookup_memories=None):
    retriever = _FakeRetriever(memories)
    neighbors = _FakeNeighborSource(rels or [])
    lookup = _FakeMemoryLookup(lookup_memories if lookup_memories is not None else memories)
    return ProjectionRetrievalService(retriever, neighbors, lookup)


# ---------------------------------------------------------------------------
# Combined retrieval + why-retrieved
# ---------------------------------------------------------------------------


def test_primary_results_carry_reasons_and_provenance() -> None:
    src = {"provenance": "wiki", "collection": "w", "path": "a.md", "section": "A"}
    m = _FakeMemory("alpha doc", primary=True, source=src, sensitivity="private")
    svc = _service([m])
    result = svc.retrieve(text_query="alpha", sensitivities=("private",))
    assert len(result.items) == 1
    item = result.items[0]
    assert REASON_PRIMARY_MATCH in item.reasons
    assert item.provenance == src
    assert "lexical" in result.diagnostics["signals_used"]
    assert "semantic" in result.diagnostics["signals_used"]
    assert result.diagnostics["why_retrieved"][0]["reasons"] == [REASON_PRIMARY_MATCH]


def test_relationship_expansion_is_bounded_by_depth() -> None:
    e1, e2, e3 = uuid4(), uuid4(), uuid4()
    seed = _FakeMemory("seed", entity_id=e1, primary=True)
    near = _FakeMemory("one hop", entity_id=e2)
    far = _FakeMemory("two hop", entity_id=e3)
    rels = [_FakeRel(e1, e2), _FakeRel(e2, e3)]
    svc = _service([seed, near, far], rels=rels)

    depth1 = svc.retrieve(text_query="seed", max_depth=1)
    contents = {i.memory.content for i in depth1.items}
    assert "one hop" in contents
    assert "two hop" not in contents  # depth bound respected

    depth2 = svc.retrieve(text_query="seed", max_depth=2)
    contents2 = {i.memory.content for i in depth2.items}
    assert "two hop" in contents2
    assert depth2.diagnostics["expansion_bounds"]["depth_reached"] == 2


def test_relationship_expansion_is_bounded_by_count() -> None:
    e1 = uuid4()
    seed = _FakeMemory("seed", entity_id=e1, primary=True)
    neighbors = [_FakeMemory(f"n{i}", entity_id=uuid4()) for i in range(5)]
    rels = [_FakeRel(e1, n.entity_id) for n in neighbors]
    svc = _service([seed, *neighbors], rels=rels)
    result = svc.retrieve(text_query="seed", max_depth=1, max_expanded=2, per_neighbor_limit=1)
    assert result.diagnostics["expanded_count"] == 2


def test_sensitivity_filters_relationship_expansion() -> None:
    e1, e2 = uuid4(), uuid4()
    seed = _FakeMemory("seed", entity_id=e1, primary=True)
    private_neighbor = _FakeMemory("private hop", entity_id=e2, sensitivity="private")
    rels = [_FakeRel(e1, e2, sensitivity="private")]
    svc = _service([seed, private_neighbor], rels=rels)

    # Only normal allowed: the private edge is not traversed.
    normal_only = svc.retrieve(text_query="seed", sensitivities=("normal",))
    assert all(i.memory.content != "private hop" for i in normal_only.items)

    # Private allowed: edge traversed and neighbor surfaced.
    with_private = svc.retrieve(text_query="seed", sensitivities=("normal", "private"))
    assert any(i.memory.content == "private hop" for i in with_private.items)
    expanded = [i for i in with_private.items if REASON_RELATIONSHIP_EXPANSION in i.reasons[0]]
    assert expanded and expanded[0].depth == 1


def test_token_budget_truncates_results() -> None:
    big = "x" * 400  # ~100 tokens each
    mems = [_FakeMemory(f"{big}{i}", primary=True) for i in range(5)]
    svc = _service(mems)
    result = svc.retrieve(text_query="x", max_tokens=150)
    assert result.diagnostics["budget_truncated"] is True
    assert len(result.items) < 5
    assert result.diagnostics["estimated_tokens"] <= 150 or len(result.items) == 1


# ---------------------------------------------------------------------------
# Exact lookup
# ---------------------------------------------------------------------------


def test_exact_lookup_by_ingest_key() -> None:
    m = _FakeMemory("exact", source={"collection": "w", "path": "a.md"})
    m.metadata_["ingest_key"] = "abc123"
    svc = _service([m])
    item = svc.lookup_exact(ingest_key="abc123")
    assert item is not None
    assert item.reasons == [REASON_EXACT_LOOKUP]
    assert svc.lookup_exact(ingest_key="missing") is None


def test_exact_lookup_by_source_location() -> None:
    src = {"provenance": "wiki", "collection": "w", "path": "a.md", "section": "A"}
    m = _FakeMemory("exact-src", source=src)
    svc = _service([m])
    item = svc.lookup_exact(collection="w", path="a.md", section="A")
    assert item is not None and item.memory.content == "exact-src"


def test_exact_ref_is_surfaced_first_in_retrieve() -> None:
    src = {"provenance": "wiki", "collection": "w", "path": "a.md", "section": "A"}
    exact = _FakeMemory("exact-doc", source=src)
    exact.metadata_["ingest_key"] = "key1"
    other = _FakeMemory("primary-doc", primary=True)
    svc = _service([exact, other])
    result = svc.retrieve(text_query="primary", exact_ref={"ingest_key": "key1"})
    assert result.items[0].reasons == [REASON_EXACT_LOOKUP]
    assert result.diagnostics["exact_hit"] is True
