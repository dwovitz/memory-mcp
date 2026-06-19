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

## Validation

`tests/ingest/test_wiki_ingest.py` covers provenance stamping, private
classification, idempotent re-runs, changed-source reindexing, removed-section
and removed-file archival, and collection-scoped isolation of the stale sweep.
