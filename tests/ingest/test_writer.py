"""Tests for IngestWriter with mocked MemoryService."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest

from memory_mcp.ingest.writer import IngestWriter


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_mem_dict(ingest_key: str, content: str = "Some content.", scope: dict | None = None) -> dict[str, Any]:
    return {
        "content": content,
        "title": "Test Section",
        "memory_type": "project_fact",
        "applies_to": scope or {"workspace": "ws", "project": "proj"},
        "metadata": {"ingest_key": ingest_key},
    }


def _make_existing_memory(ingest_key: str, content: str = "Some content.") -> MagicMock:
    mem = MagicMock()
    mem.id = uuid4()
    mem.content = content
    mem.metadata_ = {"ingest_key": ingest_key}
    mem.status = "active"
    return mem


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIngestWriter:
    """Unit tests for IngestWriter.upsert_memories."""

    def _make_writer(self, find_result: Any = None) -> tuple[IngestWriter, MagicMock]:
        """Return (writer, service_mock) with _find_by_ingest_key patched."""
        service = MagicMock()
        service.memories = MagicMock()
        service.memories.session = MagicMock()

        # Patch the session-level query used by _find_by_ingest_key
        writer = IngestWriter(service)
        writer._find_by_ingest_key = MagicMock(return_value=find_result)
        return writer, service

    def test_new_memory_is_created(self) -> None:
        """When no existing memory found, create_memory is called."""
        writer, service = self._make_writer(find_result=None)
        mem = _make_mem_dict("abc123")

        result = writer.upsert_memories([mem])

        service.create_memory.assert_called_once_with(
            content=mem["content"],
            memory_type=mem["memory_type"],
            applies_to=mem["applies_to"],
            metadata=mem["metadata"],
        )
        service.supersede_memory.assert_not_called()
        assert result == {"created": 1, "updated": 0, "skipped": 0}

    def test_identical_content_is_skipped(self) -> None:
        """When existing memory has same content, it's skipped."""
        content = "Identical content."
        existing = _make_existing_memory("key1", content=content)
        writer, service = self._make_writer(find_result=existing)
        mem = _make_mem_dict("key1", content=content)

        result = writer.upsert_memories([mem])

        service.create_memory.assert_not_called()
        service.supersede_memory.assert_not_called()
        assert result == {"created": 0, "updated": 0, "skipped": 1}

    def test_changed_content_supersedes(self) -> None:
        """When existing memory has different content, supersede_memory is called."""
        existing = _make_existing_memory("key2", content="Old content.")
        writer, service = self._make_writer(find_result=existing)
        mem = _make_mem_dict("key2", content="New content.")

        result = writer.upsert_memories([mem])

        service.supersede_memory.assert_called_once_with(
            existing.id,
            content=mem["content"],
            memory_type=mem["memory_type"],
            applies_to=mem["applies_to"],
            metadata=mem["metadata"],
        )
        service.create_memory.assert_not_called()
        assert result == {"created": 0, "updated": 1, "skipped": 0}

    def test_mixed_batch(self) -> None:
        """Mixed batch of new / updated / skipped produces correct counts."""
        existing_same = _make_existing_memory("same_key", content="Same.")
        existing_diff = _make_existing_memory("diff_key", content="Old.")

        def _find(ingest_key: str):
            return {
                "same_key": existing_same,
                "diff_key": existing_diff,
                "new_key": None,
            }[ingest_key]

        writer, service = self._make_writer()
        writer._find_by_ingest_key = MagicMock(side_effect=_find)

        memories = [
            _make_mem_dict("new_key", content="Brand new."),
            _make_mem_dict("same_key", content="Same."),
            _make_mem_dict("diff_key", content="Updated."),
        ]
        result = writer.upsert_memories(memories)

        assert result == {"created": 1, "updated": 1, "skipped": 1}
        service.create_memory.assert_called_once()
        service.supersede_memory.assert_called_once()

    def test_rerun_supersedes_not_duplicates(self) -> None:
        """Simulates running ingest twice: second run supersedes, not creates."""
        mem = _make_mem_dict("stable_key", content="Initial content.")

        # First run: no existing → create
        writer1, service1 = self._make_writer(find_result=None)
        result1 = writer1.upsert_memories([mem])
        assert result1["created"] == 1
        assert result1["updated"] == 0

        # Second run same content: existing found, same content → skip
        existing = _make_existing_memory("stable_key", content=mem["content"])
        writer2, service2 = self._make_writer(find_result=existing)
        result2 = writer2.upsert_memories([mem])
        assert result2["skipped"] == 1
        assert result2["created"] == 0
        service2.create_memory.assert_not_called()

        # Third run, updated content: existing found, different content → supersede
        updated_mem = _make_mem_dict("stable_key", content="Updated content.")
        writer3, service3 = self._make_writer(find_result=existing)
        result3 = writer3.upsert_memories([updated_mem])
        assert result3["updated"] == 1
        assert result3["created"] == 0
        service3.supersede_memory.assert_called_once()

    def test_empty_list_returns_zeros(self) -> None:
        writer, service = self._make_writer()
        result = writer.upsert_memories([])
        assert result == {"created": 0, "updated": 0, "skipped": 0}
        service.create_memory.assert_not_called()
        service.supersede_memory.assert_not_called()
