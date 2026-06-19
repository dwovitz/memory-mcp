# Implementation Order

Suggested implementation sequence for memory-mcp stories. Updated as stories are completed, blocked, or re-prioritized.

Source plan: `docs/prompts/upgrades-for-complex-program-plan.md`
Canonical backlog: `backlog/CANONICAL_BACKLOG.md`
Story index: `backlog/STORY_INDEX.csv`

## Active Next Stories (pick one)

| Order | ID | Title | Why now |
|---|---|---|---|
| 1 | MMCP-003 | Track 1: Auto-capture + distillation | Status: Ready. Spec and plan already exist. No blockers. |
| 2 | MMCP-007 | `repo` as first-class retrieval scope + GIN index | P0, no blockers. Unblocks MMCP-009, MMCP-010. |
| 3 | MMCP-006 | Workspace Ingestion Pipeline | P0, no blockers. Unblocks MMCP-011, MMCP-012, MMCP-013. |
| 4 | MMCP-008 | Semantic (vector) retrieval with HNSW | P0, no blockers. Independent of MMCP-006/007. Unblocks MMCP-012, MMCP-015. |

## Near-term (unblocked after items above ship)

| ID | Title | Blocked by |
|---|---|---|
| MMCP-009 | Code citations on memories | MMCP-007 |
| MMCP-011 | Quick Win QW1 — Markdown workspace ingest script | MMCP-006 |
| MMCP-012 | Upgrade request classifier | MMCP-006, MMCP-008 |
| MMCP-001 | Memory Dream consolidation worker | — |
| MMCP-004 | Define SafeMemoryContract | — |
| MMCP-KL-001 | Define retrieval evidence envelope | — |
| MMCP-KL-002 | Freshness and decay semantics | — |
| MMCP-KL-003 | Retrieval-grade tiers | — |

## Mid-term (blocked on near-term)

| ID | Title | Blocked by |
|---|---|---|
| MMCP-010 | QW3 — `cited_path` filter on search_memory | MMCP-009 |
| MMCP-013 | Event-flow memory types + get_event_flow | MMCP-006 |
| MMCP-014 | Multi-repo context packet diagnostics | MMCP-012 |
| MMCP-015 | Multi-repo retrieval-precision benchmarks | MMCP-008 |
| MMCP-005 | Durable compiled memory views | MMCP-004 |
| MMCP-KL-004 | Contradiction and conflict-set indexing | MMCP-KL-001 |
| MMCP-KL-005 | Progressive-disclosure context packets | MMCP-KL-003 |
| MMCP-KL-006 | Retrieval observability and audit trails | — |

## Deferred / Low priority

| ID | Title | Notes |
|---|---|---|
| MMCP-002 | Build CLI for memory-MCP | P1; unblocked but lower urgency than P0 track |

## Completed

| ID | Title | Completed |
|---|---|---|
| QW2 | `repo` parameter alias on MCP tools | 2026-05-06 |
| QW4 | `search_entities` MCP tool | 2026-05-06 |
| QW5 | Canonical `scope_path` prefix docs | 2026-05-06 |
| QW6 | Secrets guard on add_memory / supersede_memory | 2026-05-06 |
| P1-entity-graph | `upsert_entity`, `link_entities`, `traverse_entity_graph`, `get_related_memories` MCP tools | before 2026-05-14 |

## Ordering rules

1. Stories with no blockers and P0 priority go first.
2. Among unblocked P0 stories, prefer the one that unblocks the most downstream work.
3. MMCP-003 is marked Ready (spec + plan already exist); it can be started in any open slot.
4. Do not start a story whose blocker is not yet merged.
5. P2 stories are eligible only after all P0 and P1 stories in their dependency chain are complete.
