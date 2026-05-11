# memory-mcp Completion Roadmap — Design Spec

**Date:** 2026-05-11
**Status:** Approved

## Goal

Complete all remaining memory-mcp work — auto-capture/distillation, upgrades-plan P0 through P3 — and merge every track to `main`. Deliver one cold-start implementation prompt per track so each can be handed off, context cleared, and executed independently.

## What Is Already On `main`

- QW2 (`repo` param alias across MCP tools), QW4 (`search_entities` tool), QW5 (scope_path docs), QW6 (secrets guard)
- P0 workspace ingestion pipeline (`src/memory_mcp/ingest/`)
- P0 `repo` as first-class scope in `scopes.py` and MCP tool surface
- Embedding provider fixes (NullEmbeddingProvider, local_provider, vector re-rank warning)
- `feat/auto-capture-distillation` plan doc (one commit ahead of main — merged in Track 0)

## What Is Not Done

- Auto-capture + distillation (plan exists at `docs/superpowers/plans/2026-05-07-auto-capture-distillation.md`, no code)
- QW1 (markdown ingest script), QW3 (`cited_path` filter — depends on code_citations column)
- P0 semantic vector retrieval may be partial (provider exists, HNSW index/backfill/hybrid blend status unknown)
- P1 entity graph MCP tools, code citations, classifier upgrade
- P2 event-flow types, context packet diagnostics, code graph import, benchmark harness
- P3 client hook pack, hosted mode hardening
- Stale codex branches need archiving

---

## Architecture

### Prompt Chain Pattern

Each track is one self-contained cold-start prompt in `docs/prompts/`. Prompts are committed to `main` as they are written (before the track starts) so the index is always readable across sessions.

Each prompt follows this structure:

```
# Implementation Prompt — <Track Name>

Model: <Haiku | Sonnet>
Estimated effort: <range>
Branch: feat/<slug>

## Context
What this track does, what's on main, what is being added.

## Relevant files
Files to create and files to modify.

## Steps (ordered)
Numbered, file-scoped changes with exact guidance.

## Verification
- Syntax / lint checks
- pytest
- Track-specific integration check

## Merge instruction
git checkout main && git merge feat/<slug> --no-ff -m "..."

## Handoff prompt
Short snippet to paste into the next fresh session.
```

### Master Tracker

`docs/prompts/ROADMAP.md` is the single index. It contains:
- Table of all tracks with status (⬜ / ✅), model, effort, branch name, prompt file link
- "Next track" pointer updated after each merge

---

## Track Sequence

| # | Track | Prompt file | Branch | Model | Effort |
|---|---|---|---|---|---|
| 0 | Branch cleanup + ROADMAP creation | *(inline)* | main | — | 15 min |
| 1 | Auto-capture + distillation | `impl-auto-capture.md` | `feat/auto-capture-distillation` | Sonnet | 1–2 days |
| 2 | Verify / complete P0 semantic retrieval | `impl-semantic-retrieval.md` | `feat/p0-semantic-retrieval` | Sonnet | 2–4 hrs |
| 3 | QW1 markdown ingest script | `impl-qw1-markdown-ingest.md` | `feat/qw1-markdown-ingest` | Sonnet | 2–4 hrs |
| 4 | P1 entity graph MCP tools | `impl-p1-entity-graph.md` | `feat/p1-entity-graph` | Sonnet | 4–8 hrs |
| 5 | P1 code citations + QW3 `cited_path` filter | `impl-p1-code-citations.md` | `feat/p1-code-citations` | Sonnet | 4–6 hrs |
| 6 | P1 classifier upgrade (two-pass entity matching) | `impl-p1-classifier.md` | `feat/p1-classifier` | Sonnet | 4–6 hrs |
| 7 | P2 event-flow memory types + `get_event_flow` tool | `impl-p2-event-flow.md` | `feat/p2-event-flow` | Sonnet | 3–5 hrs |
| 8 | P2 context packet quality signals (multi-repo diagnostics) | `impl-p2-packet-diagnostics.md` | `feat/p2-packet-diagnostics` | Sonnet | 3–4 hrs |
| 9 | P2 `import_code_graph_summary` tool | `impl-p2-code-graph-import.md` | `feat/p2-code-graph-import` | Sonnet | 3–4 hrs |
| 10 | P2 multi-repo benchmark harness | `impl-p2-benchmarks.md` | `feat/p2-benchmarks` | Sonnet | 1 day |
| 11 | P3 client hook pack (UCX-style workspace templates) | `impl-p3-hook-pack.md` | `feat/p3-hook-pack` | Haiku | 2–4 hrs |
| 12 | P3 hosted / remote mode hardening | `impl-p3-hosted-mode.md` | `feat/p3-hosted-mode` | Sonnet | 4–8 hrs |

**Sequencing constraints:**
- Track 6 (classifier) requires Track 4 (entity store populated)
- Track 5 (code citations) must precede QW3 — they are bundled
- Track 8 (packet diagnostics) benefits from Track 6 (classifier) being done first
- Track 10 (benchmarks) should run after Tracks 2, 4, 5, 6 are merged
- Tracks 3, 4, 5 are independent and could be parallelized with multiple agents

---

## Handoff Prompt Template

At the end of each track, paste this into the next fresh session:

```
Continue memory-mcp roadmap. Track <N> (<name>) is complete and merged to main.
Next: Track <N+1> — read docs/prompts/<prompt-file>.md and implement it.
Branch off main as feat/<slug>. Use <model>.
Check docs/prompts/ROADMAP.md for current status before starting.
```

---

## Track 0 Deliverables (Inline — No Separate Prompt)

Track 0 is executed as part of this design session, not handed off:

1. Merge `feat/auto-capture-distillation` to `main` (the plan doc commit `00e35c9`)
2. Archive stale branches: `codex/outline-benchmark-runner`, `codex/source-read-contract-client-setups` (behind main — push deletion or leave as-is)
3. Create `docs/prompts/ROADMAP.md` with the full track table, all ⬜
4. Write all 12 implementation prompt files to `docs/prompts/`
5. Commit everything to `main`

---

## Error Handling and Verification Standards

Each track's prompt must include:

- **Syntax check** after any `.py` edit: `python -c "import ast; ast.parse(open('<file>').read())"`
- **Full test run**: `pytest` (or scoped to affected module)
- **Migration check** (when Alembic migration is added): `alembic upgrade head` on a clean DB
- **No secrets committed**: verify `.env` and credential files are in `.gitignore`

---

## Data Flow (Auto-Capture Track, for Reference)

```
Claude Code hooks (PostToolUse, SessionStart, UserPromptSubmit, SessionEnd)
    → enqueue_observation (MCP tool)
    → staging_observations table (Postgres)
    → DistillerService (polls FOR UPDATE SKIP LOCKED)
    → Claude API (Haiku for simple, Sonnet for complex)
    → IngestWriter (dedup, scope, lazy embedding)
    → memories table
    → get_context_packet (UserPromptSubmit hook injects into context)
```

---

## Open Questions (Resolved)

1. Scope of first integration — generic only, no ucx-root wiring.
2. Embedding model — local CPU (sentence-transformers/all-MiniLM-L6-v2, 384-dim).
3. Code graph coexistence — deferred (P2 import tool is glue-only).
4. Hosted mode timing — deferred to P3.
5. Breaking changes — `repo = project` implicit alias acceptable.
6. Personal-memory features — retained as-is.
