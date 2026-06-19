"""Tests for wiki-backed ingestion: provenance, idempotency, reindex, stale sweep.

These use an in-memory fake of the MemoryService surface that WikiIngestService
touches, so they validate orchestration deterministically without a database.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from memory_mcp.ingest.wiki import (
    WIKI_PROVENANCE,
    WikiIngestService,
    WikiSource,
    build_wiki_records,
)


# ---------------------------------------------------------------------------
# In-memory fake service
# ---------------------------------------------------------------------------


class _FakeMemory:
    def __init__(self, content: str, metadata: dict[str, Any], sensitivity: str) -> None:
        self.id = uuid4()
        self.content = content
        self.metadata_ = metadata
        self.sensitivity = sensitivity
        self.status = "active"
        self.code_citations = None


class _FakeMemories:
    def __init__(self, store: list[_FakeMemory]) -> None:
        self._store = store

    def find_active_by_metadata_key(self, field: str, value: str) -> _FakeMemory | None:
        for m in self._store:
            if m.status == "active" and (m.metadata_ or {}).get(field) == value:
                return m
        return None

    def list_active_wiki_memories(self, collection: str) -> list[_FakeMemory]:
        out = []
        for m in self._store:
            src = (m.metadata_ or {}).get("source", {})
            if (
                m.status == "active"
                and src.get("provenance") == WIKI_PROVENANCE
                and src.get("collection") == collection
            ):
                out.append(m)
        return out


class FakeMemoryService:
    """Minimal stand-in implementing the surface WikiIngestService uses."""

    def __init__(self) -> None:
        self._store: list[_FakeMemory] = []
        self.memories = _FakeMemories(self._store)

    def create_memory(
        self,
        *,
        content: str,
        memory_type: str,
        applies_to: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        sensitivity: str = "normal",
    ) -> _FakeMemory:
        mem = _FakeMemory(content, dict(metadata or {}), sensitivity)
        self._store.append(mem)
        return mem

    def supersede_memory(
        self,
        old_id: Any,
        *,
        content: str,
        memory_type: str,
        applies_to: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        sensitivity: str = "normal",
    ) -> _FakeMemory:
        for m in self._store:
            if m.id == old_id:
                m.status = "superseded"
        return self.create_memory(
            content=content,
            memory_type=memory_type,
            applies_to=applies_to,
            metadata=metadata,
            sensitivity=sensitivity,
        )

    def archive_memory(self, memory_id: Any) -> None:
        for m in self._store:
            if m.id == memory_id:
                m.status = "archived"

    # test helpers
    def active(self) -> list[_FakeMemory]:
        return [m for m in self._store if m.status == "active"]


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# build_wiki_records — provenance
# ---------------------------------------------------------------------------


def test_records_carry_full_provenance(tmp_path: Path) -> None:
    p = _write(tmp_path, "a.md", "# Title\n\nBody text.\n")
    records = build_wiki_records(
        p, collection="wiki", scope={"workspace": "ai"}, root=tmp_path
    )
    assert len(records) == 1
    meta = records[0]["metadata"]
    src = meta["source"]
    assert meta["ingest_key"]
    assert meta["content_hash"]
    assert src["provenance"] == WIKI_PROVENANCE
    assert src["collection"] == "wiki"
    assert src["path"] == "a.md"
    assert src["section"] == "Title"
    assert src["source_hash"]
    assert src["source_file_hash"]
    assert src["source_modified_time"]
    assert src["ingestion_time"]


def test_records_are_private_by_default(tmp_path: Path) -> None:
    p = _write(tmp_path, "a.md", "# T\n\nBody.\n")
    records = build_wiki_records(p, collection="wiki", scope={})
    assert records[0]["sensitivity"] == "private"


def test_ingest_key_is_stable_across_calls(tmp_path: Path) -> None:
    p = _write(tmp_path, "a.md", "# T\n\nBody.\n")
    r1 = build_wiki_records(p, collection="wiki", scope={})
    r2 = build_wiki_records(p, collection="wiki", scope={})
    assert r1[0]["metadata"]["ingest_key"] == r2[0]["metadata"]["ingest_key"]


def test_collection_changes_ingest_key(tmp_path: Path) -> None:
    p = _write(tmp_path, "a.md", "# T\n\nBody.\n")
    a = build_wiki_records(p, collection="alpha", scope={})
    b = build_wiki_records(p, collection="beta", scope={})
    assert a[0]["metadata"]["ingest_key"] != b[0]["metadata"]["ingest_key"]


def test_ingest_key_is_relative_and_posix_for_cross_platform_stability(
    tmp_path: Path,
) -> None:
    # The same relative file under two different roots (e.g. a Windows mount and
    # the matching WSL path) must share an ingest key and a POSIX ``path`` so a
    # re-ingest from another OS supersedes in place instead of archiving the old
    # set and recreating it wholesale.
    text = "# T\n\nBody.\n"
    root_a = tmp_path / "machine_a" / "wiki"
    root_b = tmp_path / "machine_b" / "wiki"
    for root in (root_a, root_b):
        (root / "sub").mkdir(parents=True)
        (root / "sub" / "a.md").write_text(text, encoding="utf-8")

    rec_a = build_wiki_records(
        root_a / "sub" / "a.md", collection="wiki", scope={}, root=root_a
    )
    rec_b = build_wiki_records(
        root_b / "sub" / "a.md", collection="wiki", scope={}, root=root_b
    )

    assert rec_a[0]["metadata"]["source"]["path"] == "sub/a.md"
    assert "\\" not in rec_a[0]["metadata"]["source"]["path"]
    assert rec_a[0]["metadata"]["ingest_key"] == rec_b[0]["metadata"]["ingest_key"]


# ---------------------------------------------------------------------------
# WikiIngestService — idempotency / reindex / stale sweep
# ---------------------------------------------------------------------------


def test_ingest_creates_then_is_idempotent(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "# One\n\nAlpha.\n\n# Two\n\nBeta.\n")
    service = FakeMemoryService()
    ingest = WikiIngestService(service)
    source = WikiSource(root=tmp_path, collection="wiki", scope={"workspace": "ai"})

    first = ingest.ingest([source])
    assert first.created == 2
    assert first.updated == 0
    assert len(service.active()) == 2

    second = ingest.ingest([source])
    assert second.created == 0
    assert second.skipped == 2
    assert second.updated == 0
    assert second.archived == 0
    assert len(service.active()) == 2


def test_ingest_classifies_records_private(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "# One\n\nAlpha.\n")
    service = FakeMemoryService()
    WikiIngestService(service).ingest([WikiSource(root=tmp_path, collection="wiki")])
    assert all(m.sensitivity == "private" for m in service.active())


def test_changed_section_supersedes(tmp_path: Path) -> None:
    f = _write(tmp_path, "a.md", "# One\n\nAlpha.\n\n# Two\n\nBeta.\n")
    service = FakeMemoryService()
    ingest = WikiIngestService(service)
    source = WikiSource(root=tmp_path, collection="wiki")
    ingest.ingest([source])

    f.write_text("# One\n\nAlpha CHANGED.\n\n# Two\n\nBeta.\n", encoding="utf-8")
    result = ingest.ingest([source])

    assert result.updated == 1
    assert result.skipped == 1
    assert result.created == 0
    # No unbounded duplicates: still exactly two active projections.
    assert len(service.active()) == 2


def test_removed_section_is_archived(tmp_path: Path) -> None:
    f = _write(tmp_path, "a.md", "# One\n\nAlpha.\n\n# Two\n\nBeta.\n")
    service = FakeMemoryService()
    ingest = WikiIngestService(service)
    source = WikiSource(root=tmp_path, collection="wiki")
    ingest.ingest([source])
    assert len(service.active()) == 2

    f.write_text("# One\n\nAlpha.\n", encoding="utf-8")  # drop "Two"
    result = ingest.ingest([source])

    assert result.archived == 1
    assert result.skipped == 1
    active = service.active()
    assert len(active) == 1
    assert "One" in active[0].content


def test_removed_file_archives_all_its_records(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "# A\n\nBody.\n")
    f2 = _write(tmp_path, "b.md", "# B1\n\nb1.\n\n# B2\n\nb2.\n")
    service = FakeMemoryService()
    ingest = WikiIngestService(service)
    source = WikiSource(root=tmp_path, collection="wiki")
    ingest.ingest([source])
    assert len(service.active()) == 3

    os.remove(f2)
    result = ingest.ingest([source])

    assert result.archived == 2
    assert len(service.active()) == 1


def test_stale_sweep_is_collection_scoped(tmp_path: Path) -> None:
    """Removing content from one collection must not archive another's records."""
    other = tmp_path / "other"
    main = tmp_path / "main"
    other.mkdir()
    main.mkdir()
    _write(other, "x.md", "# Keep\n\nstays.\n")
    f = _write(main, "y.md", "# Drop\n\ngoes.\n")

    service = FakeMemoryService()
    ingest = WikiIngestService(service)
    src_other = WikiSource(root=other, collection="other")
    src_main = WikiSource(root=main, collection="main")
    ingest.ingest([src_other, src_main])
    assert len(service.active()) == 2

    f.write_text("# Renamed\n\ngoes.\n", encoding="utf-8")  # drops "Drop" key
    result = ingest.ingest([src_main])

    # Only the "main" collection record is reconciled; "other" untouched.
    assert result.archived == 1
    sections = sorted(
        m.metadata_["source"]["section"] for m in service.active()
    )
    assert sections == ["Keep", "Renamed"]
