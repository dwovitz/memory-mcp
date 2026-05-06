"""Tests for EmbeddingProvider protocol and NullEmbeddingProvider."""

from __future__ import annotations

import pytest

from memory_mcp.embeddings.provider import EmbeddingProvider, NullEmbeddingProvider


class StubProvider:
    """Minimal stub that satisfies EmbeddingProvider."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]

    @property
    def dimensions(self) -> int:
        return 2


# ---------------------------------------------------------------------------
# NullEmbeddingProvider
# ---------------------------------------------------------------------------


def test_null_provider_embed_texts_raises() -> None:
    provider = NullEmbeddingProvider()
    with pytest.raises(RuntimeError, match="embedding disabled"):
        provider.embed_texts(["hello"])


def test_null_provider_dimensions_raises() -> None:
    provider = NullEmbeddingProvider()
    with pytest.raises(AttributeError):
        _ = provider.dimensions


# ---------------------------------------------------------------------------
# EmbeddingProvider is a Protocol
# ---------------------------------------------------------------------------


def test_embedding_provider_is_protocol() -> None:
    import typing

    assert isinstance(EmbeddingProvider, type(typing.Protocol))


# ---------------------------------------------------------------------------
# Stub satisfies the runtime-checkable protocol
# ---------------------------------------------------------------------------


def test_stub_satisfies_protocol() -> None:
    stub = StubProvider()
    assert isinstance(stub, EmbeddingProvider)


def test_null_provider_has_required_methods() -> None:
    """NullEmbeddingProvider defines the required interface methods."""
    null = NullEmbeddingProvider()
    assert callable(null.embed_texts)
    # dimensions is a property — verify it exists on the class.
    assert isinstance(type(null).dimensions, property)
