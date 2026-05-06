"""Embedding package for memory-mcp."""

from memory_mcp.embeddings.config import get_embedding_service
from memory_mcp.embeddings.provider import EmbeddingProvider, NullEmbeddingProvider
from memory_mcp.embeddings.service import EmbeddingService

__all__ = [
    "EmbeddingProvider",
    "EmbeddingService",
    "NullEmbeddingProvider",
    "get_embedding_service",
]
