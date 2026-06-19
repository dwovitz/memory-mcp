"""Tests for wiki graph projection: provenance, link resolution, stale sweep.

These use in-memory fakes of the entity/relationship repository surfaces that
WikiGraphService touches, validating deterministic projection and reconciliation
without a database (mirrors tests/ingest/test_wiki_ingest.py).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from memory_mcp.ingest.wiki import WIKI_PROVENANCE, WikiSource
from memory_mcp.ingest.wiki_graph import (
    WIKI_DOCUMENT_ENTITY_TYPE,
    WIKI_REFERENCES_RELATIONSHIP,
    WikiGraphService,
    build_wiki_graph_projection,
)


# ---------------------------------------------------------------------------
# In-memory fakes
# ---------------------------------------------------------------------------


class _FakeEntity:
    def __init__(self, entity_type, name, attributes, applies_to, sensitivity):
        self.id = uuid4()
        self.entity_type = entity_type
        self.name = name
        self.attributes = attributes
        self.applies_to = applies_to
        self.sensitivity = sensitivity
        self.status = "active"


class _FakeEntityRepo:
    def __init__(self) -> None:
        self.store: list[_FakeEntity] = []

    def upsert_provenance(
        self, *, entity_type, name, ingest_key, attributes=None, applies_to=None, sensitivity="normal"
    ):
        merged = dict(attributes or {})
        merged["ingest_key"] = ingest_key
        for e in self.store:
            if e.status == "active" and (e.attributes or {}).get("ingest_key") == ingest_key:
                e.entity_type = entity_type
                e.name = name
                e.attributes = merged
                if applies_to is not None:
                    e.applies_to = applies_to
                e.sensitivity = sensitivity
                return e, "updated"
        e = _FakeEntity(entity_type, name, merged, applies_to or {}, sensitivity)
        self.store.append(e)
        return e, "created"

    def list_active_wiki_documents(self, collection: str) -> list[_FakeEntity]:
        out = []
        for e in self.store:
            src = (e.attributes or {}).get("source", {})
            if (
                e.status == "active"
                and e.entity_type == WIKI_DOCUMENT_ENTITY_TYPE
                and src.get("provenance") == WIKI_PROVENANCE
                and src.get("collection") == collection
            ):
                out.append(e)
        return out

    def archive(self, entity_id: Any) -> None:
        for e in self.store:
            if e.id == entity_id:
                e.status = "archived"

    def active(self) -> list[_FakeEntity]:
        return [e for e in self.store if e.status == "active"]


class _FakeRelationship:
    def __init__(self, source_id, target_id, rel_type, description, metadata, applies_to, sensitivity):
        self.id = uuid4()
        self.source_entity_id = source_id
        self.target_entity_id = target_id
        self.relationship_type = rel_type
        self.description = description
        self.metadata_ = metadata
        self.applies_to = applies_to
        self.sensitivity = sensitivity
        self.status = "active"


class _FakeRelRepo:
    def __init__(self) -> None:
        self.store: list[_FakeRelationship] = []

    def upsert_provenance(
        self,
        *,
        source_entity_id,
        target_entity_id,
        relationship_type,
        ref_key,
        description=None,
        metadata=None,
        applies_to=None,
        sensitivity="normal",
    ):
        merged = dict(metadata or {})
        merged["ref_key"] = ref_key
        for r in self.store:
            if r.status == "active" and (r.metadata_ or {}).get("ref_key") == ref_key:
                r.source_entity_id = source_entity_id
                r.target_entity_id = target_entity_id
                r.relationship_type = relationship_type
                if description is not None:
                    r.description = description
                r.metadata_ = merged
                if applies_to is not None:
                    r.applies_to = applies_to
                r.sensitivity = sensitivity
                return r, "updated"
        r = _FakeRelationship(
            source_entity_id, target_entity_id, relationship_type, description, merged, applies_to or {}, sensitivity
        )
        self.store.append(r)
        return r, "created"

    def list_active_wiki_references(self, collection: str) -> list[_FakeRelationship]:
        out = []
        for r in self.store:
            src = (r.metadata_ or {}).get("source", {})
            if (
                r.status == "active"
                and r.relationship_type == WIKI_REFERENCES_RELATIONSHIP
                and src.get("provenance") == WIKI_PROVENANCE
                and src.get("collection") == collection
            ):
                out.append(r)
        return out

    def archive(self, relationship_id: Any) -> None:
        for r in self.store:
            if r.id == relationship_id:
                r.status = "archived"

    def active(self) -> list[_FakeRelationship]:
        return [r for r in self.store if r.status == "active"]


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# build_wiki_graph_projection — provenance + deterministic link resolution
# ---------------------------------------------------------------------------


def test_documents_carry_provenance_and_sensitivity(tmp_path: Path) -> None:
    a = _write(tmp_path, "a.md", "# A\n\nbody.\n")
    proj = build_wiki_graph_projection(
        [a], collection="wiki", scope={"workspace": "ai"}, sensitivity="private", root=tmp_path
    )
    assert len(proj.entities) == 1
    ent = proj.entities[0]
    assert ent.entity_type == WIKI_DOCUMENT_ENTITY_TYPE
    assert ent.sensitivity == "private"
    assert ent.applies_to == {"workspace": "ai"}
    src = ent.attributes["source"]
    assert src["provenance"] == WIKI_PROVENANCE
    assert src["collection"] == "wiki"
    assert src["path"] == "a.md"
    assert src["source_file_hash"]
    assert src["ingestion_time"]


def test_wikilink_and_markdown_link_become_references(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "# A\n\nSee [[b]] and [other](./c.md).\n")
    _write(tmp_path, "b.md", "# B\n\nbody.\n")
    _write(tmp_path, "c.md", "# C\n\nbody.\n")
    files = sorted(tmp_path.glob("*.md"))
    proj = build_wiki_graph_projection(files, collection="wiki", scope={}, root=tmp_path)

    targets = {(r.source_name, r.target_name) for r in proj.relationships}
    assert ("wiki::a.md", "wiki::b.md") in targets
    assert ("wiki::a.md", "wiki::c.md") in targets
    assert all(r.relationship_type == WIKI_REFERENCES_RELATIONSHIP for r in proj.relationships)
    assert all(r.sensitivity == "private" for r in proj.relationships)


def test_unresolved_and_self_links_are_skipped(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "# A\n\nSelf [[a]] and missing [[ghost]].\n")
    files = sorted(tmp_path.glob("*.md"))
    proj = build_wiki_graph_projection(files, collection="wiki", scope={}, root=tmp_path)
    assert proj.relationships == []


# ---------------------------------------------------------------------------
# WikiGraphService — idempotency + stale sweep
# ---------------------------------------------------------------------------


def _service():
    entities = _FakeEntityRepo()
    rels = _FakeRelRepo()
    return WikiGraphService(entities, rels), entities, rels


def test_project_is_idempotent(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "# A\n\n[[b]]\n")
    _write(tmp_path, "b.md", "# B\n\nbody.\n")
    svc, entities, rels = _service()
    source = WikiSource(root=tmp_path, collection="wiki", scope={"workspace": "ai"})

    first = svc.project([source])
    assert first.entities_created == 2
    assert first.relationships_created == 1
    assert len(entities.active()) == 2
    assert len(rels.active()) == 1

    second = svc.project([source])
    assert second.entities_created == 0
    assert second.entities_updated == 2
    assert second.relationships_created == 0
    assert second.relationships_updated == 1
    assert second.entities_archived == 0
    assert second.relationships_archived == 0
    assert len(entities.active()) == 2
    assert len(rels.active()) == 1


def test_removed_link_archives_stale_reference(tmp_path: Path) -> None:
    f = _write(tmp_path, "a.md", "# A\n\n[[b]]\n")
    _write(tmp_path, "b.md", "# B\n\nbody.\n")
    svc, entities, rels = _service()
    source = WikiSource(root=tmp_path, collection="wiki")
    svc.project([source])
    assert len(rels.active()) == 1

    f.write_text("# A\n\nno more link.\n", encoding="utf-8")
    result = svc.project([source])
    assert result.relationships_archived == 1
    assert len(rels.active()) == 0
    # Both documents still present.
    assert len(entities.active()) == 2


def test_removed_file_archives_document_and_references(tmp_path: Path) -> None:
    _write(tmp_path, "a.md", "# A\n\n[[b]]\n")
    fb = _write(tmp_path, "b.md", "# B\n\nbody.\n")
    svc, entities, rels = _service()
    source = WikiSource(root=tmp_path, collection="wiki")
    svc.project([source])
    assert len(entities.active()) == 2
    assert len(rels.active()) == 1

    os.remove(fb)
    result = svc.project([source])
    assert result.entities_archived == 1
    # The a -> b reference is no longer produced and is swept.
    assert result.relationships_archived == 1
    assert len(entities.active()) == 1
    assert len(rels.active()) == 0


def test_stale_sweep_is_collection_scoped(tmp_path: Path) -> None:
    other = tmp_path / "other"
    main = tmp_path / "main"
    other.mkdir()
    main.mkdir()
    _write(other, "x.md", "# Keep\n\nstays.\n")
    fy = _write(main, "y.md", "# Drop\n\ngoes.\n")

    svc, entities, rels = _service()
    src_other = WikiSource(root=other, collection="other")
    src_main = WikiSource(root=main, collection="main")
    svc.project([src_other, src_main])
    assert len(entities.active()) == 2

    os.remove(fy)
    result = svc.project([src_main])
    assert result.entities_archived == 1
    names = sorted(e.name for e in entities.active())
    assert names == ["other::x.md"]
