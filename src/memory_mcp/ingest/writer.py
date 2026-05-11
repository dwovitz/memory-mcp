"""IngestWriter: upsert memories via MemoryService using ingest_key deduplication."""

from __future__ import annotations

from typing import Any

from memory_mcp.models import Memory
from memory_mcp.services.memory_service import MemoryService


class IngestWriter:
    """Wraps MemoryService to provide idempotent upsert of ingested memories.

    Uses ``metadata.ingest_key`` to detect existing memories. On re-run,
    supersedes the existing memory rather than creating a duplicate.

    Note: embeddings are NOT computed at write time (lazy embedding design).
    Run ``scripts/backfill_embeddings.py`` after ingestion to populate the
    ``embedding`` column and enable vector re-ranking for ingested memories.
    """

    def __init__(self, service: MemoryService) -> None:
        self._service = service

    def _find_by_ingest_key(self, ingest_key: str) -> Memory | None:
        """Find the active memory with the given ingest_key in its metadata."""
        return self._service.memories.find_active_by_metadata_key("ingest_key", ingest_key)

    def upsert_memories(self, memories: list[dict[str, Any]]) -> dict[str, int]:
        """Upsert a list of memory dicts into the memory store.

        For each memory:
        - If no existing active memory has the same ``ingest_key``, calls
          ``create_memory`` (created += 1).
        - If an existing memory is found with the same ``ingest_key`` and
          different content, calls ``supersede_memory`` (updated += 1).
        - If content is identical, skips (skipped += 1).

        Args:
            memories: List of memory dicts. Each must have keys:
                ``content``, ``memory_type``, ``applies_to``, ``metadata``
                (with ``ingest_key``).

        Returns:
            Dict with keys ``created``, ``updated``, ``skipped``.
        """
        created = 0
        updated = 0
        skipped = 0

        for mem in memories:
            ingest_key: str = mem["metadata"]["ingest_key"]
            existing = self._find_by_ingest_key(ingest_key)
            code_citations = mem.get("code_citations")

            if existing is None:
                created_mem = self._service.create_memory(
                    content=mem["content"],
                    memory_type=mem["memory_type"],
                    applies_to=mem.get("applies_to"),
                    metadata=mem.get("metadata"),
                )
                if code_citations is not None:
                    created_mem.code_citations = code_citations
                created += 1
            elif existing.content == mem["content"]:
                skipped += 1
            else:
                updated_mem = self._service.supersede_memory(
                    existing.id,
                    content=mem["content"],
                    memory_type=mem["memory_type"],
                    applies_to=mem.get("applies_to"),
                    metadata=mem.get("metadata"),
                )
                if code_citations is not None:
                    updated_mem.code_citations = code_citations
                updated += 1

        return {"created": created, "updated": updated, "skipped": skipped}
