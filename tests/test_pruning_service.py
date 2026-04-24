"""Pruning and compression service tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from memory_mcp.models import Memory, PruningLog
from memory_mcp.pruning import PruningService


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.flush_count = 0

    def add(self, value):
        self.added.append(value)

    def flush(self) -> None:
        self.flush_count += 1


def memory(
    *,
    memory_type: str = "ephemeral_note",
    content: str = "A low-value memory.",
    summary: str | None = None,
    confidence: str = "0.800",
    status: str = "active",
    evidence=None,
    metadata=None,
    sensitivity: str = "normal",
    created_at: datetime | None = None,
    applies_to=None,
) -> Memory:
    return Memory(
        id=uuid4(),
        memory_type=memory_type,
        content=content,
        summary=summary,
        confidence=Decimal(confidence),
        status=status,
        evidence=evidence or [],
        metadata_=metadata or {},
        sensitivity=sensitivity,
        created_at=created_at or datetime.now(timezone.utc),
        applies_to=applies_to or {},
    )


def test_merge_duplicates_supersedes_lower_value_copy_and_logs() -> None:
    session = FakeSession()
    service = PruningService(session)
    keeper = memory(content="Likes concise status updates.", confidence="0.900")
    duplicate = memory(content="Likes concise status updates.", confidence="0.600")

    merged = service.merge_duplicates([keeper, duplicate])

    assert merged == 1
    assert keeper.status == "active"
    assert duplicate.status == "superseded"
    assert duplicate.metadata_["merged_into_memory_id"] == str(keeper.id)
    assert isinstance(session.added[0], PruningLog)
    assert session.added[0].action == "merge_duplicate"
    assert session.added[0].metadata_["preserved_evidence"] is True


def test_archive_stale_archives_low_value_but_preserves_evidence() -> None:
    session = FakeSession()
    service = PruningService(session)
    stale = memory(
        content="A one-off lunch note.",
        created_at=datetime.now(timezone.utc) - timedelta(days=365),
        evidence=[{"kind": "observation", "text": "Ate a sandwich."}],
    )

    archived = service.archive_stale([stale], stale_after_days=180)

    assert archived == 1
    assert stale.status == "archived"
    assert stale.evidence == [{"kind": "observation", "text": "Ate a sandwich."}]
    assert session.added[0].action == "archive_stale"


def test_archive_stale_skips_important_evidence() -> None:
    session = FakeSession()
    service = PruningService(session)
    important = memory(
        memory_type="medication",
        content="Takes cetirizine.",
        sensitivity="sensitive",
        created_at=datetime.now(timezone.utc) - timedelta(days=365),
        evidence=[{"kind": "explicit", "text": "Medication evidence."}],
    )

    archived = service.archive_stale([important], stale_after_days=180)

    assert archived == 0
    assert important.status == "active"
    assert session.added == []


def test_pruning_log_redacts_sensitive_state_snapshots() -> None:
    session = FakeSession()
    service = PruningService(session)
    sensitive = memory(
        content="Sensitive one-off detail.",
        summary="Sensitive summary.",
        sensitivity="private",
        metadata={"secret": "value"},
        created_at=datetime.now(timezone.utc) - timedelta(days=365),
    )

    archived = service.archive_stale([sensitive], stale_after_days=180)

    assert archived == 0
    assert session.added == []

    sensitive.sensitivity = "normal"
    archived = service.archive_stale([sensitive], stale_after_days=180)

    assert archived == 1
    assert session.added[0].before_state["summary"] == "Sensitive summary."

    redacted = memory(
        content="Sensitive inferred detail.",
        summary="Sensitive inferred summary.",
        sensitivity="sensitive",
        memory_type="inferred_preference",
        metadata={"capture_method": "inferred", "secret": "value"},
        created_at=datetime.now(timezone.utc) - timedelta(days=365),
    )
    service.decay_weak_inferences([redacted], half_life_days=90)

    assert session.added[1].before_state["summary"] == "[redacted]"
    assert session.added[1].before_state["metadata"]["redacted"] is True


def test_decay_weak_inference_lowers_confidence_and_can_archive() -> None:
    session = FakeSession()
    service = PruningService(session)
    inferred = memory(
        memory_type="inferred_preference",
        content="Likely likes cozy mysteries.",
        confidence="0.350",
        metadata={"capture_method": "inferred"},
        applies_to={"inferred": True},
        created_at=datetime.now(timezone.utc) - timedelta(days=200),
    )

    decayed = service.decay_weak_inferences([inferred], half_life_days=90)

    assert decayed == 1
    assert inferred.confidence < Decimal("0.350")
    assert inferred.status == "archived"
    assert session.added[0].action == "archive_weak_inference"


def test_promote_summaries_adds_summary_without_changing_content_or_evidence() -> None:
    session = FakeSession()
    service = PruningService(session)
    original_content = "This is a long project memory. It has extra implementation detail that should stay in content."
    original_evidence = [{"kind": "explicit", "text": "Important source."}]
    target = memory(content=original_content, evidence=original_evidence)

    promoted = service.promote_summaries([target], max_summary_chars=40)

    assert promoted == 1
    assert target.summary == "This is a long project memory."
    assert target.content == original_content
    assert target.evidence == original_evidence
    assert session.added[0].action == "promote_summary"


def test_run_pruning_returns_action_counts() -> None:
    session = FakeSession()
    service = PruningService(session)
    duplicate_a = memory(content="Duplicate note.", confidence="0.900")
    duplicate_b = memory(content="Duplicate note.", confidence="0.500")
    stale = memory(
        content="Stale note.",
        created_at=datetime.now(timezone.utc) - timedelta(days=365),
    )

    result = service.run_pruning(memories=[duplicate_a, duplicate_b, stale], stale_after_days=180)

    assert result.merged_duplicates == 1
    assert result.archived_stale == 1
    assert result.promoted_summaries >= 1
    assert result.total_actions == (
        result.merged_duplicates
        + result.archived_stale
        + result.decayed_inferences
        + result.promoted_summaries
    )
