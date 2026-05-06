"""EmbeddingProvider protocol and NullEmbeddingProvider."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding backends."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts, returning a list of float vectors."""
        ...

    @property
    def dimensions(self) -> int:
        """Dimensionality of the produced embeddings."""
        ...


class NullEmbeddingProvider:
    """Placeholder used when embedding is disabled; always raises."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding disabled")

    @property
    def dimensions(self) -> int:
        raise AttributeError("NullEmbeddingProvider has no dimensions — embedding is disabled")
