"""Deterministic relationship projections over canonical wiki sources.

Companion to :mod:`memory_mcp.ingest.wiki`. Where that module projects wiki
*sections* into searchable memory records (the "facts" / semantic chunks), this
module projects the wiki's *link structure* into a reviewable entity graph:

* one ``wiki_document`` entity per source file, and
* one ``references`` relationship per resolved wiki link (``[[wikilink]]`` or an
  inline Markdown link to another ``.md`` file in the same collection).

Extraction is intentionally **deterministic and reviewable** — only explicit
links to *known* documents in the same collection become edges. Nothing is
inferred by a model, and every entity and relationship carries provenance back
to its canonical source plus the collection's sensitivity label.

Like wiki ingestion, the projection is idempotent and reconcilable: re-running
over unchanged files updates the same nodes/edges, and documents (or links)
removed from the canonical wiki are archived via a collection-scoped stale
sweep so provenance is preserved and other graph data is never touched.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from memory_mcp.ingest.wiki import (
    DEFAULT_WIKI_SENSITIVITY,
    WIKI_PROVENANCE,
    WikiSource,
)

# Entity type used for every wiki document node.
WIKI_DOCUMENT_ENTITY_TYPE = "wiki_document"

# Relationship type used for every derived wiki link edge.
WIKI_REFERENCES_RELATIONSHIP = "references"

# ``[[Target]]`` or ``[[Target#anchor|alias]]`` — captures the target only.
_WIKILINK_RE = re.compile(r"\[\[\s*([^\]|#]+?)\s*(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")

# ``[label](path/to/file.md)`` or ``[label](file.md#anchor)`` — captures path.
_MD_LINK_RE = re.compile(r"\[[^\]]+\]\(\s*([^)\s]+?\.md(?:#[^)\s]*)?)\s*\)")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _document_ingest_key(collection: str, rel_path: str) -> str:
    """Stable identity for one document node within a collection."""
    return _sha256(f"{collection}::doc::{rel_path}")[:32]


def _reference_ref_key(collection: str, source_rel: str, target_rel: str) -> str:
    """Stable identity for one ``references`` edge within a collection."""
    return _sha256(f"{collection}::ref::{source_rel}::{target_rel}")[:32]


def _isoformat(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _document_name(collection: str, rel_path: str) -> str:
    """Human-readable, collection-scoped node name."""
    return f"{collection}::{rel_path}"


@dataclass
class WikiEntityProjection:
    """A provenance-stamped ``wiki_document`` entity projection."""

    entity_type: str
    name: str
    ingest_key: str
    attributes: dict[str, Any]
    applies_to: dict[str, Any]
    sensitivity: str


@dataclass
class WikiRelationshipProjection:
    """A provenance-stamped ``references`` relationship projection.

    Source and target are identified by document *name* so the service can
    resolve them to upserted entity ids after the nodes exist.
    """

    source_name: str
    target_name: str
    relationship_type: str
    ref_key: str
    description: str | None
    metadata: dict[str, Any]
    applies_to: dict[str, Any]
    sensitivity: str


@dataclass
class WikiGraphProjection:
    """The full deterministic graph projection for one wiki collection."""

    entities: list[WikiEntityProjection] = field(default_factory=list)
    relationships: list[WikiRelationshipProjection] = field(default_factory=list)


@dataclass
class WikiGraphResult:
    """Counts returned by a wiki graph projection run."""

    entities_created: int = 0
    entities_updated: int = 0
    entities_archived: int = 0
    relationships_created: int = 0
    relationships_updated: int = 0
    relationships_archived: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "entities_created": self.entities_created,
            "entities_updated": self.entities_updated,
            "entities_archived": self.entities_archived,
            "relationships_created": self.relationships_created,
            "relationships_updated": self.relationships_updated,
            "relationships_archived": self.relationships_archived,
        }


def _rel_path(path: Path, root: str | Path | None) -> str:
    source_path = str(path)
    if root is None:
        return source_path
    try:
        return str(path.relative_to(Path(root)))
    except ValueError:
        return source_path


def _link_targets(text: str) -> list[str]:
    """Return the ordered, de-duplicated raw link targets found in ``text``."""
    targets: list[str] = []
    seen: set[str] = set()
    for match in _WIKILINK_RE.finditer(text):
        target = match.group(1).strip()
        if target and target not in seen:
            seen.add(target)
            targets.append(target)
    for match in _MD_LINK_RE.finditer(text):
        target = match.group(1).split("#", 1)[0].strip()
        if target and target not in seen:
            seen.add(target)
            targets.append(target)
    return targets


def _resolution_index(rel_paths: list[str]) -> dict[str, str]:
    """Map link spellings to canonical rel paths for deterministic resolution.

    A target resolves if it matches a known document by full rel path, by rel
    path without the ``.md`` suffix, or by file stem. Stems that are ambiguous
    (shared by more than one document) are intentionally left unresolved so a
    link never silently points at the wrong file.
    """
    index: dict[str, str] = {}
    stem_counts: dict[str, int] = {}
    for rel in rel_paths:
        norm = rel.replace("\\", "/")
        index[norm] = rel
        if norm.endswith(".md"):
            index[norm[: -len(".md")]] = rel
        stem = Path(norm).stem
        stem_counts[stem] = stem_counts.get(stem, 0) + 1
    for rel in rel_paths:
        stem = Path(rel.replace("\\", "/")).stem
        if stem_counts.get(stem) == 1 and stem not in index:
            index[stem] = rel
    return index


def build_wiki_graph_projection(
    files: list[str | Path],
    *,
    collection: str,
    scope: dict[str, Any],
    sensitivity: str = DEFAULT_WIKI_SENSITIVITY,
    root: str | Path | None = None,
) -> WikiGraphProjection:
    """Project a set of wiki files into document entities and reference edges.

    Args:
        files: Source files belonging to one collection.
        collection: Stable collection id isolating this wiki's graph.
        scope: Memory scope dict (workspace/project/repo/component keys).
        sensitivity: Sensitivity label for every derived node and edge.
        root: Root used to compute provenance-friendly relative paths.

    Returns:
        A :class:`WikiGraphProjection` with deterministic, provenance-stamped
        entities and relationships. Only links to known documents in the same
        collection become edges; unresolved links are skipped.
    """
    ingestion_time = datetime.now(timezone.utc).isoformat()
    paths = [Path(f) for f in files]
    rel_by_path: dict[Path, str] = {p: _rel_path(p, root) for p in paths}
    index = _resolution_index(list(rel_by_path.values()))

    projection = WikiGraphProjection()
    text_by_path: dict[Path, str] = {}

    for path in paths:
        rel_path = rel_by_path[path]
        text = path.read_text(encoding="utf-8", errors="replace")
        text_by_path[path] = text
        source = {
            "provenance": WIKI_PROVENANCE,
            "collection": collection,
            "path": rel_path,
            "absolute_path": str(path),
            "source_file_hash": _sha256(text),
            "source_modified_time": _isoformat(path.stat().st_mtime),
            "ingestion_time": ingestion_time,
        }
        projection.entities.append(
            WikiEntityProjection(
                entity_type=WIKI_DOCUMENT_ENTITY_TYPE,
                name=_document_name(collection, rel_path),
                ingest_key=_document_ingest_key(collection, rel_path),
                attributes={"title": Path(rel_path).stem, "source": source},
                applies_to=dict(scope),
                sensitivity=sensitivity,
            )
        )

    seen_refs: set[str] = set()
    for path in paths:
        source_rel = rel_by_path[path]
        for raw_target in _link_targets(text_by_path[path]):
            norm = raw_target.replace("\\", "/")
            target_rel = index.get(norm) or index.get(Path(norm).stem)
            if target_rel is None or target_rel == source_rel:
                continue
            ref_key = _reference_ref_key(collection, source_rel, target_rel)
            if ref_key in seen_refs:
                continue
            seen_refs.add(ref_key)
            projection.relationships.append(
                WikiRelationshipProjection(
                    source_name=_document_name(collection, source_rel),
                    target_name=_document_name(collection, target_rel),
                    relationship_type=WIKI_REFERENCES_RELATIONSHIP,
                    ref_key=ref_key,
                    description=f"{source_rel} links to {target_rel}",
                    metadata={
                        "source": {
                            "provenance": WIKI_PROVENANCE,
                            "collection": collection,
                            "source_path": source_rel,
                            "target_path": target_rel,
                            "link": raw_target,
                            "ingestion_time": ingestion_time,
                        }
                    },
                    applies_to=dict(scope),
                    sensitivity=sensitivity,
                )
            )

    return projection


class _EntityPort(Protocol):
    def upsert_provenance(
        self,
        *,
        entity_type: str,
        name: str,
        ingest_key: str,
        attributes: dict[str, Any] | None = ...,
        applies_to: dict[str, Any] | None = ...,
        sensitivity: str = ...,
    ) -> tuple[Any, str]: ...

    def list_active_wiki_documents(self, collection: str) -> list[Any]: ...

    def archive(self, entity_id: UUID) -> Any: ...


class _RelationshipPort(Protocol):
    def upsert_provenance(
        self,
        *,
        source_entity_id: UUID,
        target_entity_id: UUID,
        relationship_type: str,
        ref_key: str,
        description: str | None = ...,
        metadata: dict[str, Any] | None = ...,
        applies_to: dict[str, Any] | None = ...,
        sensitivity: str = ...,
    ) -> tuple[Any, str]: ...

    def list_active_wiki_references(self, collection: str) -> list[Any]: ...

    def archive(self, relationship_id: UUID) -> Any: ...


class WikiGraphService:
    """Project wiki link structure into a reconcilable entity graph.

    Idempotent: re-running over unchanged files updates the same nodes/edges.
    Documents or links removed from the canonical wiki are archived as stale
    projections, scoped to the collection so other graph data is never touched.
    """

    def __init__(self, entities: _EntityPort, relationships: _RelationshipPort) -> None:
        self._entities = entities
        self._relationships = relationships

    def project(self, sources: list[WikiSource]) -> WikiGraphResult:
        result = WikiGraphResult()
        for source in sources:
            files: list[str | Path] = list(source.resolve_files())
            projection = build_wiki_graph_projection(
                files,
                collection=source.collection,
                scope=source.scope,
                sensitivity=source.sensitivity,
                root=source.root,
            )

            name_to_id: dict[str, UUID] = {}
            seen_entity_keys: set[str] = set()
            for ent in projection.entities:
                obj, status = self._entities.upsert_provenance(
                    entity_type=ent.entity_type,
                    name=ent.name,
                    ingest_key=ent.ingest_key,
                    attributes=ent.attributes,
                    applies_to=ent.applies_to,
                    sensitivity=ent.sensitivity,
                )
                name_to_id[ent.name] = obj.id
                seen_entity_keys.add(ent.ingest_key)
                if status == "created":
                    result.entities_created += 1
                else:
                    result.entities_updated += 1

            seen_ref_keys: set[str] = set()
            for rel in projection.relationships:
                src_id = name_to_id.get(rel.source_name)
                tgt_id = name_to_id.get(rel.target_name)
                if src_id is None or tgt_id is None:
                    continue
                _, status = self._relationships.upsert_provenance(
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relationship_type=rel.relationship_type,
                    ref_key=rel.ref_key,
                    description=rel.description,
                    metadata=rel.metadata,
                    applies_to=rel.applies_to,
                    sensitivity=rel.sensitivity,
                )
                seen_ref_keys.add(rel.ref_key)
                if status == "created":
                    result.relationships_created += 1
                else:
                    result.relationships_updated += 1

            result.relationships_archived += self._archive_stale_relationships(
                source.collection, seen_ref_keys
            )
            result.entities_archived += self._archive_stale_entities(
                source.collection, seen_entity_keys
            )
        return result

    def _archive_stale_entities(self, collection: str, seen_keys: set[str]) -> int:
        """Archive document entities in ``collection`` not produced this run."""
        archived = 0
        for entity in self._entities.list_active_wiki_documents(collection):
            key = (entity.attributes or {}).get("ingest_key")
            if key is not None and key not in seen_keys:
                self._entities.archive(entity.id)
                archived += 1
        return archived

    def _archive_stale_relationships(self, collection: str, seen_keys: set[str]) -> int:
        """Archive ``references`` edges in ``collection`` not produced this run."""
        archived = 0
        for relationship in self._relationships.list_active_wiki_references(collection):
            key = (relationship.metadata_ or {}).get("ref_key")
            if key is not None and key not in seen_keys:
                self._relationships.archive(relationship.id)
                archived += 1
        return archived
