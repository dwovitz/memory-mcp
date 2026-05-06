"""Tests for vector re-ranking in HybridRetrievalService."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from memory_mcp.retrieval.service import HybridRetrievalService, MemorySearchResult, cosine_similarity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory(content: str = "test", embedding: list[float] | None = None, confidence: float = 0.8):
    mem = MagicMock()
    mem.id = uuid4()
    mem.content = content
    mem.embedding = embedding
    mem.confidence = Decimal(str(confidence))
    mem.applies_to = {}
    mem.metadata_ = {}
    return mem


def _make_result(memory, text_rank: float = 0.5, recency_score: float = 0.5):
    return MemorySearchResult(
        memory=memory,
        rank_score=text_rank * 4 + float(memory.confidence) * 2 + recency_score,
        text_rank=text_rank,
        recency_score=recency_score,
    )


def _make_embedding_service(embed_return: list[float]):
    svc = MagicMock()
    svc.provider.embed_texts.return_value = [embed_return]
    return svc


# ---------------------------------------------------------------------------
# cosine_similarity unit tests
# ---------------------------------------------------------------------------

def test_cosine_similarity_identical():
    a = [1.0, 0.0, 0.0]
    assert cosine_similarity(a, a) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector():
    a = [0.0, 0.0]
    b = [1.0, 2.0]
    assert cosine_similarity(a, b) == 0.0


def test_cosine_similarity_known():
    a = [3.0, 4.0]
    b = [3.0, 4.0]
    assert cosine_similarity(a, b) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Re-ranking tests (no DB)
# ---------------------------------------------------------------------------

def _make_service_with_mock_candidates(candidates: list[MemorySearchResult], embedding_service=None):
    """Create a HybridRetrievalService whose DB call is mocked."""
    session = MagicMock()
    svc = HybridRetrievalService(session, embedding_service=embedding_service)

    # Patch build_search_memories_statement and session.execute
    svc.build_search_memories_statement = MagicMock(return_value=MagicMock())

    rows = []
    for r in candidates:
        row = MagicMock()
        # Bind r into default arg to avoid late-binding closure issue
        row.__getitem__ = (lambda _r: lambda self, i: _r.memory)(r)
        row.rank_score = r.rank_score
        row.text_rank = r.text_rank
        row.recency_score = r.recency_score
        rows.append(row)

    session.execute.return_value.all.return_value = rows
    return svc


def test_no_rerank_when_embedding_service_none():
    """FTS order is preserved when embedding_service is None."""
    mem_a = _make_memory("alpha", embedding=[1.0, 0.0])
    mem_b = _make_memory("beta", embedding=[0.0, 1.0])
    # a has higher FTS rank
    result_a = _make_result(mem_a, text_rank=0.9)
    result_b = _make_result(mem_b, text_rank=0.1)
    candidates = [result_a, result_b]

    svc = _make_service_with_mock_candidates(candidates, embedding_service=None)
    results = svc.search_memories(text_query="alpha", limit=2)

    assert results[0].memory is mem_a
    assert results[1].memory is mem_b


def test_no_rerank_when_no_text_query():
    """FTS order is preserved when text_query is absent."""
    mem_a = _make_memory("alpha", embedding=[1.0, 0.0])
    mem_b = _make_memory("beta", embedding=[0.0, 1.0])
    result_a = _make_result(mem_a, text_rank=0.9)
    result_b = _make_result(mem_b, text_rank=0.1)

    embedding_service = _make_embedding_service([1.0, 0.0])
    svc = _make_service_with_mock_candidates([result_a, result_b], embedding_service=embedding_service)
    results = svc.search_memories(text_query=None, limit=2)

    assert results[0].memory is mem_a
    assert results[1].memory is mem_b
    embedding_service.provider.embed_texts.assert_not_called()


def test_rerank_changes_order():
    """Re-ranking promotes memory whose embedding matches query."""
    # mem_b has FTS rank 0.1 but embedding perfectly aligned with query
    mem_a = _make_memory("alpha", embedding=[0.0, 1.0], confidence=0.8)
    mem_b = _make_memory("beta", embedding=[1.0, 0.0], confidence=0.8)
    result_a = _make_result(mem_a, text_rank=0.9, recency_score=0.5)
    result_b = _make_result(mem_b, text_rank=0.1, recency_score=0.5)

    # Query embedding aligned with mem_b [1,0]
    embedding_service = _make_embedding_service([1.0, 0.0])
    svc = _make_service_with_mock_candidates([result_a, result_b], embedding_service=embedding_service)
    results = svc.search_memories(text_query="query", limit=2)

    # mem_b should be ranked first because cosine_sim=1.0 vs 0.0
    # score_b = 0.35*1.0 + 0.35*0.1 + 0.2*0.8 + 0.1*0.5 = 0.35+0.035+0.16+0.05 = 0.595
    # score_a = 0.35*0.0 + 0.35*0.9 + 0.2*0.8 + 0.1*0.5 = 0+0.315+0.16+0.05 = 0.525
    assert results[0].memory is mem_b
    assert results[1].memory is mem_a


def test_rerank_rank_score_is_blended():
    """rank_score in returned results reflects blended formula."""
    mem = _make_memory("test", embedding=[1.0, 0.0], confidence=0.8)
    result = _make_result(mem, text_rank=0.5, recency_score=0.5)

    embedding_service = _make_embedding_service([1.0, 0.0])
    svc = _make_service_with_mock_candidates([result], embedding_service=embedding_service)
    results = svc.search_memories(text_query="test", limit=1)

    # cosine_sim = 1.0, text_rank=0.5, confidence=0.8, recency=0.5
    expected = 0.35 * 1.0 + 0.35 * 0.5 + 0.2 * 0.8 + 0.1 * 0.5
    assert results[0].rank_score == pytest.approx(expected)


def test_none_embedding_gets_zero_cosine():
    """Memories with embedding=None are not skipped; they get cosine_sim=0."""
    mem_a = _make_memory("has-emb", embedding=[1.0, 0.0], confidence=0.8)
    mem_b = _make_memory("no-emb", embedding=None, confidence=0.8)
    result_a = _make_result(mem_a, text_rank=0.1, recency_score=0.5)
    result_b = _make_result(mem_b, text_rank=0.9, recency_score=0.5)

    # Query aligned with mem_a
    embedding_service = _make_embedding_service([1.0, 0.0])
    svc = _make_service_with_mock_candidates([result_a, result_b], embedding_service=embedding_service)
    results = svc.search_memories(text_query="test", limit=2)

    # score_a = 0.35*1.0+0.35*0.1+0.2*0.8+0.1*0.5 = 0.35+0.035+0.16+0.05 = 0.595
    # score_b = 0.35*0.0+0.35*0.9+0.2*0.8+0.1*0.5 = 0+0.315+0.16+0.05 = 0.525
    assert results[0].memory is mem_a
    assert results[1].memory is mem_b


def test_fallback_to_fts_on_provider_error():
    """If provider.embed_texts raises, fall back to FTS order."""
    mem_a = _make_memory("alpha", embedding=[1.0, 0.0])
    mem_b = _make_memory("beta", embedding=[0.0, 1.0])
    result_a = _make_result(mem_a, text_rank=0.9)
    result_b = _make_result(mem_b, text_rank=0.1)
    candidates = [result_a, result_b]

    embedding_service = MagicMock()
    embedding_service.provider.embed_texts.side_effect = RuntimeError("model not loaded")

    svc = _make_service_with_mock_candidates(candidates, embedding_service=embedding_service)
    results = svc.search_memories(text_query="alpha", limit=2)

    # FTS order preserved: a first
    assert results[0].memory is mem_a
    assert results[1].memory is mem_b


def test_limit_applied_after_rerank():
    """Only `limit` results are returned after re-ranking."""
    memories = [_make_memory(f"mem{i}", embedding=[float(i), 0.0]) for i in range(10)]
    results_in = [_make_result(m, text_rank=float(i) / 10) for i, m in enumerate(memories)]

    embedding_service = _make_embedding_service([1.0, 0.0])
    svc = _make_service_with_mock_candidates(results_in, embedding_service=embedding_service)
    results = svc.search_memories(text_query="test", limit=3)

    assert len(results) == 3


def test_candidate_expansion_when_reranking():
    """When reranking, build_search_memories_statement is called with expanded limit."""
    session = MagicMock()
    embedding_service = _make_embedding_service([1.0, 0.0])
    svc = HybridRetrievalService(session, embedding_service=embedding_service)

    build_mock = MagicMock(return_value=MagicMock())
    svc.build_search_memories_statement = build_mock
    session.execute.return_value.all.return_value = []

    svc.search_memories(text_query="query", limit=10)

    # Candidate limit should be max(10*5, 50) = 50
    call_kwargs = build_mock.call_args[1]
    assert call_kwargs["limit"] == 50
