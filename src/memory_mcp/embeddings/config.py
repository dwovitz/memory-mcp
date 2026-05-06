"""Embedding configuration and service factory."""

from __future__ import annotations

import os

EMBEDDING_ENABLED: bool = os.getenv("MEMORY_MCP_EMBEDDING_ENABLED", "false").lower() == "true"
EMBEDDING_MODEL: str = os.getenv("MEMORY_MCP_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIMENSIONS: int = int(os.getenv("MEMORY_MCP_EMBEDDING_DIMENSIONS", "384"))


def get_embedding_service(db_session=None):
    """Return an EmbeddingService if embedding is enabled, else None."""
    if not EMBEDDING_ENABLED:
        return None
    from .local_provider import LocalEmbeddingProvider  # noqa: PLC0415
    from .service import EmbeddingService  # noqa: PLC0415

    provider = LocalEmbeddingProvider(EMBEDDING_MODEL)
    return EmbeddingService(provider, db_session)
