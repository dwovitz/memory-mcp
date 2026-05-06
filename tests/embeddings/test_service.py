"""Tests for EmbeddingService."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest

from memory_mcp.embeddings.service import EmbeddingService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_provider(dims: int = 3, vector_factory=None):
    provider = MagicMock()
    provider.dimensions = dims
    if vector_factory is None:
        provider.embed_texts.side_effect = lambda texts: [[0.1] * dims for _ in texts]
    else:
        provider.embed_texts.side_effect = vector_factory
    return provider


def make_session():
    session = MagicMock()
    session.execute.return_value = MagicMock()
    return session


# ---------------------------------------------------------------------------
# embed_and_store
# ---------------------------------------------------------------------------


def test_embed_and_store_calls_provider_and_writes() -> None:
    provider = make_provider()
    session = make_session()
    service = EmbeddingService(provider, session)

    memory_id = uuid4()
    service.embed_and_store(memory_id, "hello world")

    provider.embed_texts.assert_called_once_with(["hello world"])
    session.execute.assert_called_once()
    session.commit.assert_called_once()


def test_embed_and_store_passes_memory_id_to_query() -> None:
    provider = make_provider()
    session = make_session()
    service = EmbeddingService(provider, session)

    memory_id = uuid4()
    service.embed_and_store(memory_id, "test content")

    call_kwargs = session.execute.call_args[0][1]
    assert call_kwargs["id"] == str(memory_id)


# ---------------------------------------------------------------------------
# Content-hash cache
# ---------------------------------------------------------------------------


def test_cache_prevents_duplicate_embed_calls() -> None:
    provider = make_provider()
    session = make_session()
    service = EmbeddingService(provider, session)

    id1 = uuid4()
    id2 = uuid4()
    service.embed_and_store(id1, "identical content")
    service.embed_and_store(id2, "identical content")

    # Provider should only be called once for the same content.
    provider.embed_texts.assert_called_once_with(["identical content"])
    # But DB writes happen twice (two different memory rows).
    assert session.execute.call_count == 2
    assert session.commit.call_count == 2


def test_cache_is_keyed_by_content_not_id() -> None:
    provider = make_provider()
    session = make_session()
    service = EmbeddingService(provider, session)

    id1 = uuid4()
    id2 = uuid4()
    service.embed_and_store(id1, "content A")
    service.embed_and_store(id2, "content B")

    assert provider.embed_texts.call_count == 2


# ---------------------------------------------------------------------------
# embed_batch
# ---------------------------------------------------------------------------


def test_embed_batch_processes_all_items() -> None:
    provider = make_provider()
    session = make_session()
    service = EmbeddingService(provider, session)

    items = [(uuid4(), f"content {i}") for i in range(5)]
    service.embed_batch(items)

    # All 5 unique texts passed to provider in one call.
    provider.embed_texts.assert_called_once()
    called_texts = provider.embed_texts.call_args[0][0]
    assert len(called_texts) == 5
    assert session.execute.call_count == 5
    assert session.commit.call_count == 5


def test_embed_batch_deduplicates_identical_content() -> None:
    provider = make_provider()
    session = make_session()
    service = EmbeddingService(provider, session)

    id1, id2, id3 = uuid4(), uuid4(), uuid4()
    items = [(id1, "same"), (id2, "same"), (id3, "different")]
    service.embed_batch(items)

    # Provider called once with 2 unique texts.
    provider.embed_texts.assert_called_once()
    called_texts = provider.embed_texts.call_args[0][0]
    assert set(called_texts) == {"same", "different"}
    # But 3 DB writes.
    assert session.execute.call_count == 3


def test_embed_batch_empty_list_is_noop() -> None:
    provider = make_provider()
    session = make_session()
    service = EmbeddingService(provider, session)

    service.embed_batch([])

    provider.embed_texts.assert_not_called()
    session.execute.assert_not_called()


def test_embed_batch_uses_cache_across_calls() -> None:
    """Content cached from a prior embed_and_store is reused in embed_batch."""
    provider = make_provider()
    session = make_session()
    service = EmbeddingService(provider, session)

    id1 = uuid4()
    service.embed_and_store(id1, "cached content")
    provider.embed_texts.reset_mock()

    id2 = uuid4()
    service.embed_batch([(id2, "cached content")])

    # Provider should NOT be called again.
    provider.embed_texts.assert_not_called()
