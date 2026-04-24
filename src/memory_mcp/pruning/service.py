"""Pruning and compression service for memory records."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from memory_mcp.models import Memory, PruningLog


IMPORTANT_MEMORY_TYPES = {
    "medication",
    "personal_fact",
    "project_fact",
    "app_knowledge",
}


@dataclass(frozen=True)
class PruningRunResult:
    """Summary of pruning actions taken in one run."""

    merged_duplicates: int = 0
    archived_stale: int = 0
    decayed_inferences: int = 0
    promoted_summaries: int = 0

    @property
    def total_actions(self) -> int:
        return (
            self.merged_duplicates
            + self.archived_stale
            + self.decayed_inferences
            + self.promoted_summaries
        )


class PruningService:
    """Reduce memory noise while preserving valuable evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def run_pruning(
        self,
        *,
        stale_after_days: int = 180,
        inference_half_life_days: int = 90,
        memories: Sequence[Memory] | None = None,
    ) -> PruningRunResult:
        candidate_memories = list(memories) if memories is not None else self._load_active_memories()
        merged = self.merge_duplicates(candidate_memories)
        archived = self.archive_stale(candidate_memories, stale_after_days=stale_after_days)
        decayed = self.decay_weak_inferences(
            candidate_memories,
            half_life_days=inference_half_life_days,
        )
        promoted = self.promote_summaries(candidate_memories)
        return PruningRunResult(
            merged_duplicates=merged,
            archived_stale=archived,
            decayed_inferences=decayed,
            promoted_summaries=promoted,
        )

    def merge_duplicates(self, memories: Sequence[Memory]) -> int:
        """Archive duplicate active memories by superseding lower-value copies."""

        grouped: dict[tuple[Any, ...], list[Memory]] = defaultdict(list)
        for memory in memories:
            if memory.status != "active":
                continue
            grouped[_duplicate_key(memory)].append(memory)

        merged = 0
        for duplicates in grouped.values():
            if len(duplicates) < 2:
                continue
            keeper = _best_memory(duplicates)
            for duplicate in duplicates:
                if duplicate is keeper:
                    continue
                self._supersede_duplicate(duplicate, keeper)
                merged += 1
        return merged

    def archive_stale(
        self,
        memories: Sequence[Memory],
        *,
        stale_after_days: int = 180,
        now: datetime | None = None,
    ) -> int:
        """Archive old low-value memories without deleting evidence."""

        current_time = now or datetime.now(timezone.utc)
        cutoff = current_time - timedelta(days=stale_after_days)
        archived = 0

        for memory in memories:
            created_at = _aware_datetime(memory.created_at)
            if memory.status != "active" or created_at is None or created_at >= cutoff:
                continue
            if _has_important_evidence(memory):
                continue

            before = _memory_state(memory)
            memory.status = "archived"
            self._log(
                memory,
                action="archive_stale",
                reason=f"Archived stale low-value memory older than {stale_after_days} days.",
                before_state=before,
                after_state=_memory_state(memory),
                confidence=memory.confidence,
            )
            archived += 1
        return archived

    def decay_weak_inferences(
        self,
        memories: Sequence[Memory],
        *,
        half_life_days: int = 90,
        archive_below: Decimal = Decimal("0.300"),
        now: datetime | None = None,
    ) -> int:
        """Lower confidence of old inferred memories and archive very weak ones."""

        current_time = now or datetime.now(timezone.utc)
        decayed = 0

        for memory in memories:
            if memory.status != "active" or not _is_inferred(memory):
                continue
            created_at = _aware_datetime(memory.created_at)
            if created_at is None:
                continue
            age_days = max(0, (current_time - created_at).days)
            if age_days < half_life_days:
                continue

            before = _memory_state(memory)
            current_confidence = Decimal(memory.confidence or 0)
            decay_steps = max(1, age_days // half_life_days)
            decayed_confidence = current_confidence * (Decimal("0.75") ** decay_steps)
            memory.confidence = max(Decimal("0.000"), decayed_confidence.quantize(Decimal("0.001")))
            action = "decay_inference"
            reason = f"Decayed weak inference after {age_days} days."
            if memory.confidence < archive_below and not _has_important_evidence(memory):
                memory.status = "archived"
                action = "archive_weak_inference"
                reason = f"Archived weak inferred memory below confidence {archive_below}."

            self._log(
                memory,
                action=action,
                reason=reason,
                before_state=before,
                after_state=_memory_state(memory),
                confidence=memory.confidence,
            )
            decayed += 1
        return decayed

    def promote_summaries(self, memories: Sequence[Memory], *, max_summary_chars: int = 180) -> int:
        """Create compact summaries while preserving original content and evidence."""

        promoted = 0
        for memory in memories:
            if memory.status not in {"active", "archived", "superseded"}:
                continue
            new_summary = _summary_for(memory.content, max_chars=max_summary_chars)
            if not new_summary:
                continue
            if memory.summary and len(memory.summary) <= max_summary_chars:
                continue

            before = _memory_state(memory)
            memory.summary = new_summary
            self._log(
                memory,
                action="promote_summary",
                reason="Created compact summary from memory content.",
                before_state=before,
                after_state=_memory_state(memory),
                confidence=memory.confidence,
            )
            promoted += 1
        return promoted

    def _supersede_duplicate(self, duplicate: Memory, keeper: Memory) -> None:
        before = _memory_state(duplicate)
        duplicate.status = "superseded"
        duplicate.superseded_at = datetime.now(timezone.utc)
        duplicate.metadata_ = {
            **(duplicate.metadata_ or {}),
            "merged_into_memory_id": str(keeper.id),
        }
        self._log(
            duplicate,
            action="merge_duplicate",
            reason=f"Merged duplicate memory into {keeper.id}.",
            before_state=before,
            after_state=_memory_state(duplicate),
            confidence=duplicate.confidence,
        )

    def _log(
        self,
        memory: Memory,
        *,
        action: str,
        reason: str,
        before_state: dict[str, Any],
        after_state: dict[str, Any],
        confidence: Decimal | str | float | None,
    ) -> PruningLog:
        log = PruningLog(
            memory_id=memory.id,
            action=action,
            reason=reason,
            confidence=confidence,
            sensitivity=memory.sensitivity,
            status="applied",
            applies_to=memory.applies_to or {},
            before_state=before_state,
            after_state=after_state,
            metadata_={
                "preserved_evidence": True,
                "service": "PruningService",
            },
        )
        self.session.add(log)
        self.session.flush()
        return log

    def _load_active_memories(self) -> list[Memory]:
        return list(self.session.scalars(select(Memory).where(Memory.status == "active")))


def _duplicate_key(memory: Memory) -> tuple[Any, ...]:
    return (
        memory.entity_id,
        memory.memory_type,
        _normalize_text(memory.summary or memory.content),
        json.dumps(memory.applies_to or {}, sort_keys=True),
    )


def _best_memory(memories: Sequence[Memory]) -> Memory:
    return max(
        memories,
        key=lambda memory: (
            _has_important_evidence(memory),
            Decimal(memory.confidence or 0),
            len(memory.evidence or []),
            _aware_datetime(memory.created_at) or datetime.min.replace(tzinfo=timezone.utc),
        ),
    )


def _has_important_evidence(memory: Memory) -> bool:
    metadata = memory.metadata_ or {}
    if metadata.get("important") is True or metadata.get("pin") is True:
        return True
    if memory.sensitivity in {"sensitive", "private"}:
        return True
    if memory.memory_type in IMPORTANT_MEMORY_TYPES:
        return True

    for item in memory.evidence or []:
        if not isinstance(item, dict):
            continue
        if item.get("important") is True:
            return True
        if item.get("kind") in {"explicit", "source", "document"} and item.get("text"):
            return True
    return False


def _is_inferred(memory: Memory) -> bool:
    metadata = memory.metadata_ or {}
    applies_to = memory.applies_to or {}
    return (
        memory.memory_type.startswith("inferred")
        or metadata.get("capture_method") == "inferred"
        or applies_to.get("inferred") is True
    )


def _summary_for(content: str | None, *, max_chars: int) -> str | None:
    if not content:
        return None
    stripped = " ".join(content.split())
    if not stripped:
        return None
    first_sentence = stripped.split(". ", 1)[0].strip()
    if len(first_sentence) <= max_chars:
        return first_sentence if first_sentence.endswith(".") else f"{first_sentence}."
    return f"{first_sentence[: max_chars - 1].rstrip()}..."


def _memory_state(memory: Memory) -> dict[str, Any]:
    redacted = memory.sensitivity in {"sensitive", "private"}
    metadata = memory.metadata_ or {}
    return {
        "id": str(memory.id),
        "status": memory.status,
        "confidence": str(memory.confidence) if memory.confidence is not None else None,
        "evidence_count": len(memory.evidence or []),
        "redacted": redacted,
        "summary": "[redacted]" if redacted else memory.summary,
        "metadata": {"keys": sorted(metadata), "redacted": True} if redacted else metadata,
    }


def _normalize_text(text: str | None) -> str:
    return " ".join((text or "").casefold().split())


def _aware_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
