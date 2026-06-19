# Wiki-Backed Ingestion

`memory-mcp` can index a local, file-based wiki as the **canonical source** of
private human-readable knowledge. The wiki stays canonical; `memory-mcp` stores
derived **projections** — searchable, scoped, deduplicated memory records that
carry provenance back to their source section.

## Canonical source vs. projection

| Responsibility | Owner |
|---|---|
| Authoring and editing knowledge | The wiki (canonical) |
| Source of truth for content | The wiki (canonical) |
| Searchable derived records, chunks, embeddings, entities, summaries | `memory-mcp` (projection) |
| Provenance, sensitivity, lifecycle of projections | `memory-mcp` (projection) |

`memory-mcp` never edits wiki files. It only reads them and reconciles its
derived records to match. If the wiki and the projections disagree, the wiki
wins and the projection is updated or archived.

## Provenance

Each derived record is one Markdown section (one ATX heading). Every record is
stamped with provenance under `metadata.source`:

| Field | Meaning |
|---|---|
| `provenance` | Always `"wiki"`; scopes the stale-projection sweep |
| `collection` | Stable id isolating one wiki's projections |
| `path` | Source path (relative to the wiki root) |
| `absolute_path` | Absolute source path |
| `section` | Heading breadcrumb (e.g. `Parent > Child`) |
| `source_hash` | SHA-256 of the section's projected content |
| `source_file_hash` | SHA-256 of the whole source file |
| `source_modified_time` | Source file mtime (ISO 8601, UTC) |
| `ingestion_time` | When this projection was written (ISO 8601, UTC) |

The record's top-level `metadata.ingest_key` is a stable hash of
`collection :: source_path :: section`. Including the collection prevents
cross-collection key collisions, so reconciling one wiki never touches another.

## Sensitivity and privacy

Wiki content is canonical **private** knowledge. Derived records default to
`sensitivity = "private"`, so the derived chunks and any embeddings computed
from them inherit a private classification. This is the default for
`WikiSource` and the `scripts/ingest_wiki.py` CLI; override only when a wiki is
known to be non-sensitive.

## Reindex and supersession lifecycle

Ingestion is deterministic and reconciling:

- **Unchanged section** → skipped. No new row, no new `ingestion_time`. Re-runs
  over an unchanged wiki are fully idempotent.
- **Changed section** (content hash differs) → the prior projection is
  superseded by a new active record with the same `ingest_key`. No unbounded
  duplicates accumulate.
- **Removed section** (heading deleted or renamed) → its projection is no longer
  produced by the run, so the collection-scoped stale sweep **archives** it.
- **Removed file** → every projection for that file is archived by the same
  sweep.

### Stale-projection policy

Removal is handled by **archiving** (status `archived`), not hard-deleting.
Archiving preserves provenance and is reversible; a later re-appearance of the
section creates a fresh active projection. The sweep is scoped to a single
`collection`, so removing content from one wiki never archives another's
records.

## Usage

```bash
python scripts/ingest_wiki.py \
    --collection home-wiki \
    --root /path/to/wiki \
    --workspace ai --project memory-mcp \
    --sensitivity private

# Preview projections without writing:
python scripts/ingest_wiki.py --collection home-wiki --root /path/to/wiki --dry-run
```

Programmatically:

```python
from memory_mcp.db import session_scope
from memory_mcp.ingest.wiki import WikiIngestService, WikiSource
from memory_mcp.services.memory_service import MemoryService

with session_scope() as session:
    service = MemoryService(session)
    result = WikiIngestService(service).ingest([
        WikiSource(root="/path/to/wiki", collection="home-wiki",
                   scope={"workspace": "ai", "project": "memory-mcp"}),
    ])
    session.commit()

# result.created / .updated / .skipped / .archived
```

After ingestion, run `scripts/backfill_embeddings.py` to populate embeddings for
the new projections (embeddings are computed lazily, not at write time).

## Graph projection

Alongside the per-section memory projections (the "facts" / semantic chunks),
`memory-mcp` projects the wiki's **link structure** into a reviewable entity
graph via `WikiGraphService`:

- one `wiki_document` **entity** per source file, and
- one `references` **relationship** per resolved link.

Extraction is **deterministic and reviewable**. Only explicit links to *known*
documents in the same collection become edges:

- `[[wikilink]]` (with optional `#anchor` and `|alias`), and
- inline Markdown links to another `.md` file (`[text](path/to/file.md)`).

Targets resolve by full relative path, by path without the `.md` suffix, or by an
**unambiguous** file stem. Ambiguous stems, self-links, and links to unknown
documents are skipped, so an edge never silently points at the wrong file.
Nothing is inferred by a model.

Every entity and relationship carries provenance and the source's sensitivity:

| Projection | Identity | Provenance |
|---|---|---|
| `wiki_document` entity | `attributes.ingest_key` = hash(`collection :: doc :: path`) | `attributes.source` (collection, path, file hash, times) |
| `references` relationship | `metadata.ref_key` = hash(`collection :: ref :: src :: tgt`) | `metadata.source` (collection, source/target paths, link, time) |

The graph projection shares the wiki's reconciliation guarantees: re-running over
unchanged files updates the same nodes/edges, and documents or links removed from
the canonical wiki are archived by a **collection-scoped stale sweep** so other
graph data is never touched. The `scripts/ingest_wiki.py` CLI runs the graph
projection automatically after section ingestion and prints the entity/edge
counts. See [retrieval.md](retrieval.md) for how these projections are queried
with bounded relationship expansion.

## Validation

`tests/ingest/test_wiki_ingest.py` covers provenance stamping, private
classification, idempotent re-runs, changed-source reindexing, removed-section
and removed-file archival, and collection-scoped isolation of the stale sweep.

`tests/ingest/test_wiki_graph.py` covers deterministic document/reference
projection, wikilink and Markdown-link resolution, idempotency, and
collection-scoped archival of stale documents and references.
