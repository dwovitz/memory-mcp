"""IngestWriter: upsert memories via MemoryService using ingest_key deduplication."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from memory_mcp.models import Memory
from memory_mcp.services.memory_service import MemoryService


class IngestWriter:
    """Wraps MemoryService to provide idempotent upsert of ingested memories.

    Uses ``metadata.ingest_key`` to detect existing memories. On re-run,
    supersedes the existing memory rather than creating a duplicate.
    """

    def __init__(self, service: MemoryService) -> None:
        self._service = service

    def _find_by_ingest_key(self, ingest_key: str) -> Memory | None:
        """Find the active memory with the given ingest_key in its metadata."""
        session: Session = self._service.memories.session
        # metadata_ is mapped to the "metadata" JSONB column.
        # Use the ->> text operator to extract the ingest_key field as text.
        stmt = (
            select(Memory)
            .where(Memory.status == "active")
            .where(Memory.metadata_["ingest_key"].astext == ingest_key)
        )
        return session.scalars(stmt).first()

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

            if existing is None:
                self._service.create_memory(
                    content=mem["content"],
                    memory_type=mem["memory_type"],
                    applies_to=mem.get("applies_to"),
                    metadata=mem.get("metadata"),
                )
                created += 1
            elif existing.content == mem["content"]:
                skipped += 1
            else:
                self._service.supersede_memory(
                    existing.id,
                    content=mem["content"],
                    memory_type=mem["memory_type"],
                    applies_to=mem.get("applies_to"),
                    metadata=mem.get("metadata"),
                )
                updated += 1

        return {"created": created, "updated": updated, "skipped": skipped}
