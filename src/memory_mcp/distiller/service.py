from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Protocol

from memory_mcp.db import session_scope
from memory_mcp.distiller.prompts import build_distillation_messages
from memory_mcp.distiller.router import ModelChoice, select_model
from memory_mcp.ingest.writer import IngestWriter
from memory_mcp.repositories.staging import StagingRepository
from memory_mcp.services.memory_service import MemoryService

log = logging.getLogger(__name__)


class _AnthropicLike(Protocol):
    @property
    def messages(self) -> Any: ...


class DistillerService:
    """Polls staging_observations, distills batches, promotes typed memories."""

    def __init__(self, *, client: _AnthropicLike, worker_id: str,
                 max_tokens: int = 4096) -> None:
        self._client = client
        self._worker_id = worker_id
        self._max_tokens = max_tokens

    def distill_once(self, *, batch_size: int = 25) -> int:
        """Process at most one batch. Returns number of staging rows handled."""
        with session_scope() as s:
            staging = StagingRepository(s)
            rows = staging.claim_batch(limit=batch_size, worker_id=self._worker_id)
            if not rows:
                return 0
            batch = [
                {"source": r.source, "payload": r.payload, "scope": r.scope}
                for r in rows
            ]
            row_ids = [r.id for r in rows]
            s.commit()  # release row locks before the LLM call

        model = select_model(batch)
        system, user = build_distillation_messages(batch)
        try:
            resp = self._client.messages.create(
                model=model.value,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = resp.content[0].text
            entries = json.loads(text)
            if not isinstance(entries, list):
                raise ValueError(f"expected list, got {type(entries).__name__}")
        except Exception as exc:
            log.warning("distillation failed for %d rows: %s", len(row_ids), exc)
            with session_scope() as s:
                staging = StagingRepository(s)
                for rid in row_ids:
                    staging.mark_failed(rid, str(exc)[:500])
                s.commit()
            return len(row_ids)

        # Promote entries via IngestWriter (handles dedupe + scope routing).
        with session_scope() as s:
            writer = IngestWriter(MemoryService(session=s))
            normalized = [self._normalize(e) for e in entries]
            writer.upsert_memories(normalized)
            staging = StagingRepository(s)
            for rid in row_ids:
                staging.mark_done(rid)
            s.commit()
        return len(row_ids)

    @staticmethod
    def _normalize(entry: dict) -> dict:
        entry = dict(entry)  # copy to avoid mutating caller's data

        # Extract top-level ingest_key (LLM emits it at the top level)
        ingest_key = entry.pop("ingest_key", None)

        metadata = dict(entry.get("metadata") or {})

        if not ingest_key:
            ingest_key = metadata.get("ingest_key")
        if not ingest_key:
            payload = json.dumps(
                {"c": entry.get("content", ""), "s": entry.get("applies_to", {})},
                sort_keys=True,
            )
            ingest_key = "distill:" + hashlib.sha256(payload.encode()).hexdigest()[:16]

        metadata["ingest_key"] = ingest_key

        # Move confidence/tags into metadata so IngestWriter doesn't receive unknown keys
        for key in ("confidence", "tags"):
            if key in entry:
                metadata[key] = entry.pop(key)

        entry["metadata"] = metadata
        return entry
