"""Local sentence-transformers embedding provider."""

from __future__ import annotations


class LocalEmbeddingProvider:
    """Embedding provider backed by a local sentence-transformers model.

    sentence_transformers is imported lazily inside __init__ so the
    package is not required unless this provider is actually instantiated.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        # Lazy import — sentence_transformers is an optional dependency.
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        self._model = SentenceTransformer(model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings as pure-Python float lists."""
        return [v.tolist() for v in self._model.encode(texts, convert_to_numpy=False)]

    @property
    def dimensions(self) -> int:
        return self._model.get_sentence_embedding_dimension()
