"""EmbeddingService: compute and persist embeddings for memories."""

from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import text

from memory_mcp.embeddings.provider import EmbeddingProvider


class EmbeddingService:
    """Wraps an EmbeddingProvider and writes vectors to the memories table."""

    def __init__(self, provider: EmbeddingProvider, db_session) -> None:
        self._provider = provider
        self._session = db_session
        self._cache: dict[str, list[float]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _content_key(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_embedding(self, content: str) -> list[float]:
        key = self._content_key(content)
        if key not in self._cache:
            vectors = self._provider.embed_texts([content])
            self._cache[key] = vectors[0]
        return self._cache[key]

    def _write_embedding(self, memory_id: UUID, embedding: list[float]) -> None:
        self._session.execute(
            text("UPDATE memories SET embedding = :emb WHERE id = :id"),
            {"emb": embedding, "id": str(memory_id)},
        )
        self._session.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def provider(self) -> EmbeddingProvider:
        """Expose the query-embedding provider without exposing service state."""
        return self._provider

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed query text without persisting it as a memory embedding."""
        return self._provider.embed_texts(texts)

    def embed_and_store(self, memory_id: UUID, content: str) -> None:
        """Compute embedding for *content* and write it to the DB row."""
        embedding = self._get_embedding(content)
        self._write_embedding(memory_id, embedding)

    def embed_batch(self, items: list[tuple[UUID, str]]) -> None:
        """Embed and store a batch of (memory_id, content) pairs.

        Identical content strings are deduplicated via the content-hash cache.
        """
        if not items:
            return

        # Collect unique contents not already cached.
        unique_contents: list[str] = []
        seen_keys: set[str] = set()
        for _, content in items:
            key = self._content_key(content)
            if key not in self._cache and key not in seen_keys:
                unique_contents.append(content)
                seen_keys.add(key)

        # Batch-embed uncached contents.
        if unique_contents:
            vectors = self._provider.embed_texts(unique_contents)
            for content, vector in zip(unique_contents, vectors):
                self._cache[self._content_key(content)] = vector

        # Write all.
        for memory_id, content in items:
            embedding = self._cache[self._content_key(content)]
            self._write_embedding(memory_id, embedding)
