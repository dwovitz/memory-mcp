"""Wiki-backed ingestion with provenance, sensitivity, and reindexing.

The local file-based wiki is treated as the *canonical* source of truth for
private human-readable knowledge. ``memory-mcp`` stores derived memory records
as **projections** of that wiki: searchable, scoped, deduplicated copies that
carry provenance back to their source.

Responsibilities of this module:

* Parse a wiki collection (Markdown files) into one record per section.
* Stamp each record with provenance — source path, source section, content
  hash, source file hash, source modified time, and ingestion time.
* Classify derived records (and therefore their embeddings and chunks) with a
  sensitivity label. Wiki content defaults to ``private``.
* Drive idempotent ingestion via :class:`~memory_mcp.ingest.writer.IngestWriter`.
* Detect and archive *stale projections* — derived records whose source
  section or whole source file was removed or excluded since the last run.

The wiki remains canonical; ``memory-mcp`` never edits wiki files. Removal is
handled by archiving (not hard-deleting) the derived record so provenance and
recoverability are preserved.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory_mcp.ingest.parser import parse_markdown_headings
from memory_mcp.ingest.writer import IngestWriter

# Provenance marker stored under ``metadata.source.provenance``. Used to scope
# the stale-projection sweep so wiki ingestion never touches unrelated memories.
WIKI_PROVENANCE = "wiki"

# Default sensitivity for wiki-derived records. Wiki content is canonical
# private knowledge, so derived chunks and embeddings are treated as private.
DEFAULT_WIKI_SENSITIVITY = "private"

DEFAULT_WIKI_GLOBS = ("**/*.md", "**/*.markdown")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ingest_key(collection: str, source_path: str, section: str) -> str:
    """Stable identifier for one derived record within a collection.

    Including the collection prevents cross-collection key collisions so the
    stale sweep for one wiki never archives records projected from another.
    """
    raw = f"{collection}::{source_path}::{section}"
    return _sha256(raw)[:32]


def _isoformat(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


@dataclass
class WikiSource:
    """A wiki collection to ingest as projections of canonical private content.

    Args:
        root: Directory (or single file) holding the canonical wiki content.
        collection: Stable identifier isolating this wiki's projections. The
            stale-projection sweep is scoped to a single collection.
        scope: Memory scope dict (workspace/project/repo/component keys).
        sensitivity: Sensitivity label for every derived record. Defaults to
            ``private`` so derived chunks and embeddings are private data.
        globs: Glob patterns (relative to ``root``) selecting source files.
    """

    root: Path
    collection: str
    scope: dict[str, Any] = field(default_factory=dict)
    sensitivity: str = DEFAULT_WIKI_SENSITIVITY
    globs: tuple[str, ...] = DEFAULT_WIKI_GLOBS

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        if not self.collection:
            raise ValueError("WikiSource.collection must be a non-empty string")
        valid = {"normal", "sensitive", "private"}
        if self.sensitivity not in valid:
            raise ValueError(
                f"Invalid sensitivity {self.sensitivity!r}. Must be one of: {valid}"
            )

    def resolve_files(self) -> list[Path]:
        """Return the sorted, de-duplicated set of source files to ingest."""
        if self.root.is_file():
            return [self.root]
        files: list[Path] = []
        for pattern in self.globs:
            files.extend(p for p in self.root.glob(pattern) if p.is_file())
        return sorted(set(files))


@dataclass
class WikiIngestResult:
    """Counts returned by a wiki ingestion run."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    archived: int = 0

    def merge(self, other: dict[str, int]) -> None:
        self.created += other.get("created", 0)
        self.updated += other.get("updated", 0)
        self.skipped += other.get("skipped", 0)
        self.archived += other.get("archived", 0)

    def as_dict(self) -> dict[str, int]:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "archived": self.archived,
        }


def build_wiki_records(
    file_path: str | Path,
    *,
    collection: str,
    scope: dict[str, Any],
    sensitivity: str = DEFAULT_WIKI_SENSITIVITY,
    root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Project one Markdown file into provenance-stamped memory records.

    Each ATX heading becomes one record. The record carries full provenance so
    the projection can be traced to — and reconciled against — its canonical
    source section.

    Returns:
        A list of memory dicts ready for
        :meth:`~memory_mcp.ingest.writer.IngestWriter.upsert_memories`. Each has
        ``content``, ``memory_type``, ``applies_to``, ``sensitivity``, and a
        ``metadata`` block with ``ingest_key``, ``content_hash``, and a nested
        ``source`` provenance object.
    """
    path = Path(file_path)
    source_path = str(path)
    file_text = path.read_text(encoding="utf-8", errors="replace")
    source_file_hash = _sha256(file_text)
    source_modified_time = _isoformat(path.stat().st_mtime)
    ingestion_time = datetime.now(timezone.utc).isoformat()
    rel_path = source_path
    if root is not None:
        try:
            rel_path = str(path.relative_to(Path(root)))
        except ValueError:
            rel_path = source_path

    records: list[dict[str, Any]] = []
    for section in parse_markdown_headings(path):
        breadcrumb = section.heading_path + [section.heading]
        section_label = " > ".join(breadcrumb)
        if section.body:
            content = f"{'#' * section.level} {section.heading}\n\n{section.body}"
        else:
            content = f"{'#' * section.level} {section.heading}"
        content_hash = _sha256(content)
        ingest_key = _ingest_key(collection, source_path, section_label)
        records.append(
            {
                "content": content,
                "memory_type": "project_fact",
                "applies_to": dict(scope),
                "sensitivity": sensitivity,
                "metadata": {
                    "ingest_key": ingest_key,
                    "content_hash": content_hash,
                    "source": {
                        "provenance": WIKI_PROVENANCE,
                        "collection": collection,
                        "path": rel_path,
                        "absolute_path": source_path,
                        "section": section_label,
                        "source_hash": content_hash,
                        "source_file_hash": source_file_hash,
                        "source_modified_time": source_modified_time,
                        "ingestion_time": ingestion_time,
                    },
                },
            }
        )
    return records


class WikiIngestService:
    """Ingest wiki collections as deterministic, reconcilable projections.

    The service is idempotent: re-running over unchanged files skips every
    record (no new ingestion timestamp, no duplicate rows). Changed sections
    supersede their prior projection. Sections or files removed from the
    canonical wiki are archived as stale projections, scoped to the collection
    so other memories are never touched.
    """

    def __init__(self, service: Any) -> None:
        self._service = service
        self._writer = IngestWriter(service)

    def ingest(self, sources: list[WikiSource]) -> WikiIngestResult:
        result = WikiIngestResult()
        for source in sources:
            files = source.resolve_files()
            seen_keys: set[str] = set()
            records: list[dict[str, Any]] = []
            for file_path in files:
                file_records = build_wiki_records(
                    file_path,
                    collection=source.collection,
                    scope=source.scope,
                    sensitivity=source.sensitivity,
                    root=source.root,
                )
                records.extend(file_records)
                seen_keys.update(r["metadata"]["ingest_key"] for r in file_records)

            result.merge(self._writer.upsert_memories(records))
            archived = self._archive_stale(source.collection, seen_keys)
            result.archived += archived
        return result

    def _archive_stale(self, collection: str, seen_keys: set[str]) -> int:
        """Archive active projections in ``collection`` no longer present.

        Any active wiki memory whose ``ingest_key`` was not produced by the
        current run (its source section or file was removed or excluded) is
        archived. Archiving preserves provenance and is reversible, unlike a
        hard delete.
        """
        existing = self._service.memories.list_active_wiki_memories(collection)
        archived = 0
        for memory in existing:
            key = (memory.metadata_ or {}).get("ingest_key")
            if key is not None and key not in seen_keys:
                self._service.archive_memory(memory.id)
                archived += 1
        return archived
