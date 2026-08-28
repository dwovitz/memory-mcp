# memory-mcp

PostgreSQL + pgvector memory service with MCP interface. Provides durable project memory across Claude and Codex sessions via Docker.

memory-mcp is a **retrieval/projection service**, not an unchecked runtime assistant. Every agent working in this repository must satisfy the issue readiness contract before beginning implementation.

## AI Index Startup And Closeout

Before broad exploration, read repository context in this order:

1. `AGENTS.md`
2. `AI_INDEX.md`
3. `AI_ARCHITECTURE.md`
4. the active GitHub issue and any tool-specific instructions
5. memory/context and code-review-graph tools
6. only the narrow source paths identified by that context

`AI_INDEX.md` is a navigation map, not a replacement for source verification.
Use `python scripts/ai_index_check.py --base origin/main` before closeout when
a branch changes MCP contracts, storage, retrieval, scopes, safety, Docker,
major entrypoints, or generated-index boundaries. Refresh only the
automation-owned region with `python scripts/ai_index_refresh.py`.

Every closeout must state whether the AI index was reviewed, which index files
changed, and why no update was needed when the check does not require one.

## Issue Readiness — Execution Contract

Full contract: `.memory-mcp/issue-contract.md`

**Before beginning any implementation**, verify all of the following or abort and report:

1. `status:ready` label is present on the issue (hard requirement — missing = immediate abort).
2. Readiness score ≥ 0.7 (see scoring table in the contract).
3. Required sections present and non-empty: Phase, Goal, Scope, Out of scope, Acceptance criteria, Dependency, `## AI documentation impact`.
4. `## AI documentation impact` uses a recognized form (`updates-required:` list or `no-update-needed:` with rationale).
5. Route label is present: `route:outer-harness` or `route:inner-harness`.

**Fail closed**: if any check fails, stop, report the specific missing items, and do not proceed.

## Outer-Harness Execution

Full guidance: `.memory-mcp/outer-run.md`

Key rules for outer-harness runs:

- Fetch `origin/main` and branch from it: `git fetch origin && git checkout -b mmcp-{n}-{slug} origin/main`
- Run `pytest tests/ -x -q` and `mypy src/ --ignore-missing-imports` before committing
- Resolve `## AI documentation impact` before opening the PR
- PR must not be a draft; include `Closes #{n}` and an outer-run trace in the body
- `route:inner-harness` is not currently configured — stop and ask if you see it

## Route Labels

| Label | Meaning |
|---|---|
| `route:outer-harness` | AI implements directly (Claude Code or Codex CLI) — default |
| `route:inner-harness` | Not yet configured; stop and request clarification |

## Code Exploration — Graph First

Always use code-review-graph MCP tools before grep or file reads:

- `semantic_search_nodes` to find functions or classes by name/keyword
- `get_impact_radius` before any edit to understand blast radius
- `query_graph` with callers_of/callees_of to trace call chains
- `detect_changes` + `get_review_context` for code review
- Fall back to file reads only when the graph doesn't cover what you need.

## Model Routing (Codex)

| Work type | Model | Effort |
|---|---|---|
| File search, log scanning, read-only exploration | `gpt-5.4-mini` | low |
| Documentation and contract updates | `gpt-5.1-codex` | med |
| Schema or migration changes | `gpt-5.1-codex` | high |
| Retrieval logic, context assembly, embedding pipeline | `gpt-5.1-codex` | high |
| Privacy / PII handling, data minimization | `gpt-5.5-codex` | high |
| Security review, auth, broad architecture | `gpt-5.5-codex` | high |
| Implementation + tests (standard) | `gpt-5.1-codex` | med–high |
| Adversarial review | `gpt-5.5-codex` | high |

- `gpt-5.4-mini` subagents are read-only — no file edits.
- Always cap `gpt-5.4-mini` briefs: "report in under 150 words" or "return a structured list only".
- If a listed model is unavailable, use the closest available smaller model for read-only work and the inherited model for implementation.
- See `.memory-mcp/outer-run.md` for the full model/effort table covering both Claude and Codex.

## Agent Dispatch Patterns

Spawn a subagent when:
- A task is purely read-only (search, summarize, scan) — use `gpt-5.4-mini`
- Two or more independent tasks can run in parallel — dispatch both simultaneously
- A task would produce large output the main session doesn't need verbatim

Brief format: task goal + relevant paths/scope + output format + word cap.

## Memory

Use `memory-mcp` as the durable context layer for the same workflows Claude Code uses.

Before substantial implementation, review, debugging, or planning, call `get_context_packet` with the narrowest useful scope:

```text
workspace="ai"
project="memory-mcp"
repo="memory-mcp"       # optional: narrows to this repo within the project
component="<subsystem when clear>"
include_global=true
include_sensitive=false
```

Inspect `context_quality`, `warnings`, `suggested_next_action`, `source_read_policy`, and `source_read_budget_tokens` before reading source. If context is weak or misses the project/component, retry once at project scope before broad source reads.

**Within-session caching:** After the first `get_context_packet` call in a conversation, save the version token from `get_memory_cache_state` or from the response. On every subsequent `get_context_packet` call in the same session, pass `if_cache_version: <saved_token>`. If the server returns `{"cached": True}`, reuse the previous packet — no tokens consumed. The server detects memory changes automatically and returns a fresh packet when the version changes.

For source reads:
- `answer_from_packet`: answer from memory and skip source reads.
- `verify_narrowly`: read only the specific snippets needed to confirm the packet.
- `mark_weak_context`: inspect source before answering, but keep reads bounded.

When storing memories with `add_memory`, include `repo="memory-mcp"` in the scope for finer routing.

After meaningful changes, refresh memory with compact, non-sensitive project facts, decisions, commands, constraints, and workflow updates. Never store secrets, credentials, raw logs, transcripts, or sensitive customer data.

## Knowledge Ingestion

A local file-based wiki is the **canonical** source of private human-readable knowledge. `memory-mcp` stores **projections** of it — searchable derived records with provenance (`metadata.source`), classified `private` by default. Treat the wiki as the source of truth; never make `memory-mcp` the canonical editor of wiki content, and do not hand-author memories that duplicate canonical wiki sections — run wiki ingestion instead (`scripts/ingest_wiki.py`, `memory_mcp.ingest.wiki.WikiIngestService`). Ingestion is idempotent: unchanged sections are skipped, changed sections supersede, and removed sections/files are archived. Wiki link structure is also projected deterministically into `wiki_document` entities and `references` relationships (provenance-stamped, same stale sweep) so retrieval can do bounded relationship expansion; never hand-author graph edges that duplicate wiki links. See [docs/wiki_ingestion.md](docs/wiki_ingestion.md) and [docs/retrieval.md](docs/retrieval.md).
