# Retrieval and Projection

`memory-mcp` is the local **semantic and graph projection layer** over canonical
sources (notably the [wiki](wiki_ingestion.md)). It does not make the database
the manual source of truth: it stores *projections* — semantic chunks, and
entity/fact/relationship graph nodes — that always carry provenance back to the
canonical source, and it returns bounded, provenance-backed context.

There are two cooperating layers:

| Layer | Class | Responsibility |
|---|---|---|
| Hybrid ranking | `HybridRetrievalService` | Lexical + semantic + structured + recency + confidence ranking over memories/entities |
| Projection retrieval | `ProjectionRetrievalService` | Combines hybrid ranking with bounded relationship expansion, exact lookup, and *why-retrieved* explanations |

## Projection types and provenance

| Projection | Stored as | Provenance | Sensitivity |
|---|---|---|---|
| Semantic chunk / fact | `memories` row (one per wiki section) | `metadata.source` (path, section, hashes, times) | `private` by default for wiki |
| Document entity | `entities` row (`entity_type = wiki_document`) | `attributes.source` + `attributes.ingest_key` | inherited from the source |
| Reference relationship | `relationships` row (`relationship_type = references`) | `metadata.source` + `metadata.ref_key` | inherited from the source |

Entity and relationship projections are produced by deterministic, reviewable
extraction only — see [wiki_ingestion.md](wiki_ingestion.md#graph-projection).
No projection is created without provenance.

## Durable compiled views

A durable compiled view is a bounded, reusable orientation projection over
source memories. It is distinct from a request-time context packet and remains
derived rather than canonical. Views need foreign-key-backed source provenance,
scope/sensitivity limits, lifecycle-aware invalidation, and explicit
source-verification guidance. See [compiled_memory_views.md](compiled_memory_views.md).

## Combined retrieval

`ProjectionRetrievalService.retrieve(...)` blends every available signal:

- **Lexical** — PostgreSQL full-text rank over content and summary.
- **Semantic** — embedding cosine re-rank when an embedding service is present.
- **Structured filters** — memory type, tags, `applies_to`, scope, status.
- **Recency** and **confidence** — folded into the rank score.
- **Relationship expansion** — bounded traversal of the wiki entity graph.

Each returned `RetrievedItem` carries:

- `reasons` — why it was retrieved: `primary_match`,
  `relationship_expansion:<type>@depth<n>`, or `exact_lookup`.
- `provenance` — the item's `metadata.source` block.
- `depth` / `via_relationship` — how far (and via which edge) it was reached.

The result's `diagnostics` includes `signals_used`, `why_retrieved`, the
expansion bounds actually applied, and the token accounting.

## Bounded relationship expansion

Expansion can never grow without limit. It is bounded by:

| Bound | Parameter | Effect |
|---|---|---|
| Graph depth | `max_depth` | Maximum hops from a primary result |
| Result count | `max_expanded` | Maximum expanded (depth > 0) items added |
| Per-neighbor | `per_neighbor_limit` | Memories pulled per neighbor entity |
| Sensitivity | `sensitivities` | Edges/neighbors outside the allowed set are skipped |
| Context budget | `max_tokens` | Stops adding items once the estimated size would exceed the budget |

Sensitivity bounding applies to **both** the primary search and expansion, so a
`normal`-only request never traverses a `private` wiki edge.

## Exact lookup

Deterministic references stay available alongside fuzzy recall:

- by projection `ingest_key`, or
- by canonical source location (`collection` + `path` [+ `section`]).

`lookup_exact(...)` resolves a single projection; `retrieve(..., exact_ref=...)`
surfaces it first in the result set and records `exact_hit` in diagnostics.

## Stale and superseded projections

When canonical content changes, derived projections are reconciled (see
[wiki_ingestion.md](wiki_ingestion.md)):

- changed sections **supersede** their prior chunk;
- removed sections/files **archive** their chunk;
- removed documents and links **archive** the derived entities and `references`
  relationships, scoped by `collection` so other graph data is untouched.

## Validation

- `tests/test_projection_retrieval.py` — combined retrieval, depth/count/
  sensitivity/budget bounds, exact lookup, and why-retrieved reasons.
- `tests/ingest/test_wiki_graph.py` — deterministic graph projection, link
  resolution, idempotency, and collection-scoped stale sweep.
- `tests/test_hybrid_retrieval*.py` — lexical/semantic/structured ranking.
