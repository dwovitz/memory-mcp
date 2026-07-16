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
from memory_mcp.safety import check_content_for_secrets
from memory_mcp.services.memory_service import MemoryService

log = logging.getLogger(__name__)

MAX_BATCH_SIZE = 8
MAX_OUTPUT_ENTRIES = 16
MAX_CONTENT_CHARS = 2_000
MAX_INGEST_KEY_CHARS = 128
MAX_TAGS = 25
MAX_TAG_CHARS = 100
MAX_SCOPE_VALUE_CHARS = 200
VALID_MEMORY_TYPES = frozenset(
    {
        "project_fact",
        "architecture_decision",
        "coding_preference",
        "workflow_location",
        "dependency",
        "project_rule",
        "external_reference",
        "component_summary",
        "app_knowledge",
    }
)
VALID_SCOPE_KEYS = frozenset({"workspace", "project", "repo", "component"})
VALID_ENTRY_FIELDS = frozenset(
    {"memory_type", "content", "confidence", "tags", "applies_to", "observation_ids", "ingest_key"}
)


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

    def distill_once(self, *, batch_size: int = MAX_BATCH_SIZE) -> int:
        """Process at most one batch. Returns number of staging rows handled."""
        batch_size = max(1, min(batch_size, MAX_BATCH_SIZE))
        with session_scope() as s:
            staging = StagingRepository(s)
            rows = staging.claim_batch(limit=batch_size, worker_id=self._worker_id)
            if not rows:
                return 0
            batch = [
                {
                    "observation_id": str(r.id),
                    "source": r.source,
                    "payload": r.payload,
                    "scope": r.scope,
                }
                for r in rows
            ]
            row_ids = [r.id for r in rows]
            claimed_observations = {
                str(r.id): {"source": str(r.source), "scope": dict(r.scope or {})}
                for r in rows
            }
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
        # Provenance is assigned by the service, never trusted to model output.
        try:
            with session_scope() as s:
                writer = IngestWriter(MemoryService(session=s))
                if len(entries) > MAX_OUTPUT_ENTRIES:
                    raise ValueError(
                        f"distiller output must not exceed {MAX_OUTPUT_ENTRIES} entries"
                    )
                normalized = [
                    self._normalize(e, claimed_observations=claimed_observations)
                    for e in entries
                ]
                writer.upsert_memories(normalized)
                staging = StagingRepository(s)
                for rid in row_ids:
                    staging.mark_done(rid)
                s.commit()
        except Exception as exc:
            log.warning("promotion failed for %d rows: %s", len(row_ids), exc)
            with session_scope() as s:
                staging = StagingRepository(s)
                for rid in row_ids:
                    staging.mark_failed(rid, str(exc)[:500])
                s.commit()
        return len(row_ids)

    @staticmethod
    def _normalize(
        entry: dict[str, Any], *, claimed_observations: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        if not isinstance(entry, dict):
            raise ValueError("each distilled entry must be a JSON object")
        unknown_fields = set(entry) - VALID_ENTRY_FIELDS
        if unknown_fields:
            raise ValueError(f"unsupported distiller output fields: {sorted(unknown_fields)}")

        memory_type = entry.get("memory_type")
        if memory_type not in VALID_MEMORY_TYPES:
            raise ValueError("unsupported memory_type")
        content = entry.get("content")
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_CONTENT_CHARS:
            raise ValueError(f"content must be a non-empty string up to {MAX_CONTENT_CHARS} characters")
        check_content_for_secrets(content)

        confidence = entry.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be a number from 0.0 through 1.0")
        tags = entry.get("tags")
        if (
            not isinstance(tags, list)
            or len(tags) > MAX_TAGS
            or any(not isinstance(tag, str) or not tag or len(tag) > MAX_TAG_CHARS for tag in tags)
        ):
            raise ValueError(f"tags must be a list of at most {MAX_TAGS} short strings")

        observation_ids = entry.get("observation_ids")
        if (
            not isinstance(observation_ids, list)
            or not observation_ids
            or any(not isinstance(obs_id, str) for obs_id in observation_ids)
            or len(set(observation_ids)) != len(observation_ids)
            or not set(observation_ids).issubset(claimed_observations)
        ):
            raise ValueError("observation_ids must be a non-empty unique subset of claimed observations")

        applies_to = entry.get("applies_to")
        if not isinstance(applies_to, dict) or set(applies_to) - VALID_SCOPE_KEYS:
            raise ValueError("applies_to must contain only supported scope keys")
        selected_scopes = [claimed_observations[obs_id]["scope"] for obs_id in observation_ids]
        if any(scope != selected_scopes[0] for scope in selected_scopes[1:]):
            raise ValueError("cited observations must share the same scope")
        common_scope = {
            key: value
            for key, value in selected_scopes[0].items()
            if key in VALID_SCOPE_KEYS
        }
        if (
            applies_to != common_scope
            or any(
                not isinstance(value, str) or not value or len(value) > MAX_SCOPE_VALUE_CHARS
                for value in applies_to.values()
            )
        ):
            raise ValueError("applies_to must exactly match the common cited observation scope")

        ingest_key = entry.get("ingest_key")
        if not isinstance(ingest_key, str) or not ingest_key or len(ingest_key) > MAX_INGEST_KEY_CHARS:
            payload = json.dumps({"c": content, "s": applies_to}, sort_keys=True)
            ingest_key = "distill:" + hashlib.sha256(payload.encode()).hexdigest()[:16]

        metadata = {
            "ingest_key": ingest_key,
            "source": "auto_capture",
            "observation_ids": observation_ids,
            "observation_sources": sorted(
                {str(claimed_observations[obs_id]["source"]) for obs_id in observation_ids}
            ),
            "confidence": confidence,
            "tags": tags,
        }
        return {
            "memory_type": memory_type,
            "content": content,
            "applies_to": applies_to,
            "metadata": metadata,
            # Staged session material is private until an explicit review/promotion
            # path can classify it for normal retrieval.
            "sensitivity": "private",
        }
