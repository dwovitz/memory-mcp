# AI Index

## Repo Purpose

`memory-mcp` is a PostgreSQL + pgvector memory service with an MCP interface. It provides durable project and personal memory across Claude, Codex, and related local agent sessions.

It should be treated as a scalable second-brain memory layer, not just a Claude helper.

## Index Philosophy

This file is a compact navigation layer. It should help agents decide where to start, what not to break, and which source-of-truth files, graph/context tools, and validation paths to use next.

It is not a complete semantic index, an embedding replacement, or a summary of every source file. Prefer small, reviewable maps that remain accurate over broad generated summaries that become stale.

## Current Status

Active. The repo supports durable memory workflows, project context retrieval, graph/entity memory, and agent-context reduction patterns.

## Required Startup Context

Agents should read these before broad exploration:

1. `AGENTS.md`
2. `AI_INDEX.md`
3. `AI_ARCHITECTURE.md`
4. Tool-specific instructions such as `CLAUDE.md` or `CODEX.md`
5. Relevant GitHub Issue/story
6. Graph/context tools
7. Narrow source files identified by graph/context tools and the issue

Use code-review-graph MCP tools before grep or broad file reads when available.

## Main Entry Points

| Path | Purpose |
|---|---|
| `AGENTS.md` | Shared agent source of truth. |
| `CLAUDE.md` | Claude-specific expanded guidance; should defer to shared repo policy. |
| `AI_INDEX.md` | This repo navigation and operating map. |
| `AI_ARCHITECTURE.md` | Memory service architecture, boundaries, and contracts. |
| `docs/ai-indexing.md` | Shared maintenance rules for AI-facing index files. |
| Source directories | MCP server, storage, retrieval, entity graph, and related implementation. |
| Tests | Validation for memory behavior, storage, retrieval, and APIs. |
| Docker files | Local/server runtime and persistence setup. |

<!-- AI-GENERATED:START repo-map -->
## Generated Repository Map

| Path | Responsibility |
|---|---|
| `.memory-mcp/` | Issue readiness and outer-harness execution contracts. |
| `src/memory_mcp/` | Service package: MCP, persistence, retrieval, authorization, ingestion, and lifecycle features. |
| `src/memory_mcp/mcp_tools/` | MCP server and public tool definitions. |
| `src/memory_mcp/auth/` | Trusted-local and remote principal, grant, OIDC, and proxy controls. |
| `src/memory_mcp/ingest/` | Markdown/wiki parsing, provenance-aware writing, and graph projection. |
| `src/memory_mcp/retrieval/` | Hybrid retrieval and relationship-aware projection. |
| `src/memory_mcp/distiller/` | Staged-observation distillation service and worker runner. |
| `src/memory_mcp/models/` | SQLAlchemy schema and shared persistence types. |
| `src/memory_mcp/repositories/` | Database repositories for memories, entities, relationships, audit, and staging. |
| `migrations/` | Alembic migration environment and ordered schema revisions. |
| `hooks/` | Client-side capture hooks; they must remain bounded and non-blocking. |
| `scripts/` | Operator utilities, ingestion/backfill helpers, and AI-index commands. |
| `tests/` | Pytest coverage grouped by service capability and integration boundary. |
| `docs/` | Canonical operator, architecture, ingestion, retrieval, and workflow documentation. |
| `client-setups/` | Thin, client-specific connection/setup examples. |
| `benchmarks/` | Repeatable context-reduction benchmark cases and results. |
| `docker-compose.yml` | Postgres, MCP gateway, and background-distiller development topology. |
| `pyproject.toml` | Python packaging, runtime dependencies, and pytest configuration. |
<!-- AI-GENERATED:END repo-map -->

## Critical Concepts

- Memory is a durable context layer for multiple harnesses, not a provider-specific feature.
- Project memory and personal memory should remain distinguishable.
- Retrieval should reduce token usage by surfacing relevant context packets before source reads.
- SQLite should not be assumed as the right scalable/server default; storage should be evaluated against deployment target.
- Memory should store compact facts, decisions, rules, commands, constraints, and project context — not raw transcripts, secrets, or sensitive data. Auto-capture is authorized at enqueue, bounded before distillation, promotes only private claims, and retains server-validated staging provenance on promotion.
- Use the smallest meaningful validation loop for the change; do not default to expensive full-repo validation when a targeted check proves the contract.
- AI index updates are part of story closeout when navigation, commands, contracts, architecture, MCP behavior, storage/retrieval behavior, or generated-file boundaries change.

## Starting Paths By Change Type

| Change | Start here | Focused validation |
|---|---|---|
| MCP contract or transport | `src/memory_mcp/mcp_tools/server.py`, `src/memory_mcp/main.py`, `tests/test_mcp_tools.py` | `pytest tests/test_mcp_tools.py -x -q` |
| Retrieval or context packet | `src/memory_mcp/retrieval/`, `src/memory_mcp/services/context_synthesis.py`, `docs/retrieval.md` | retrieval/context tests plus source-read-policy coverage |
| Memory schema or lifecycle | `src/memory_mcp/models/`, `src/memory_mcp/repositories/`, `migrations/` | model/repository/migration tests |
| Authentication or sensitivity | `src/memory_mcp/auth/`, `src/memory_mcp/mcp_tools/server.py` | auth-policy and MCP tests |
| Wiki/markdown ingestion | `src/memory_mcp/ingest/`, `docs/wiki_ingestion.md` | ingestion test package |
| Auto-capture/distillation | `hooks/`, `src/memory_mcp/mcp_tools/server.py`, `src/memory_mcp/distiller/`, `src/memory_mcp/repositories/staging.py`, `docs/auto_capture.md` | MCP authorization/bounds plus hook, staging, and distiller tests |
| Conversation evidence design | `docs/conversation_ingestion.md`, `docs/auto_capture.md`, `docs/ARCHITECTURE.md` | documentation link/contract review; do not add runtime storage in the design slice |
| Runtime/deployment | `Dockerfile`, `docker-compose.yml`, `.env.example`, `README.md` | compose configuration and relevant runtime probe |

## Do Not Break

- MCP compatibility.
- Context packet workflow.
- Scope fields such as workspace, project, repo, and component.
- Sensitive-data boundaries.
- Durable storage compatibility and migration expectations.
- Cross-agent usability for Claude, Codex, and local harnesses.
- The separation between human-authored intent and generated AI index regions.

## How To Explore

1. Read `AGENTS.md`.
2. Read this file and `AI_ARCHITECTURE.md`.
3. Use memory/context and code-review-graph tools before broad file reads.
4. Inspect only relevant implementation and tests.
5. Avoid broad GitHub search unless the index and graph do not identify useful paths.

For broad read-only exploration, prefer a bounded mapper/research step that returns a compact file/path summary before implementation begins.

## AI Index Maintenance

Update this file when a change modifies:

- memory service purpose or boundaries;
- MCP contracts or tool behavior;
- storage/retrieval architecture;
- scope model;
- sensitive-data policy;
- Docker/deployment assumptions;
- graph/entity memory model;
- cross-agent workflow expectations;
- validation commands or scoped test guidance;
- generated-file boundaries.

See `docs/ai-indexing.md` for maintenance rules.

## Machine-Readable Index Commands

- `python scripts/ai_index_check.py --base origin/main` verifies required files,
  generated-region freshness, and whether architecture-sensitive diffs include
  an index review.
- `python scripts/ai_index_refresh.py` refreshes only the marked generated
  region in this file and `.ai/index.json`.

The checker intentionally treats `AGENTS.md`, `AI_INDEX.md`,
`AI_ARCHITECTURE.md`, `docs/ai-indexing.md`, and `.ai/index.json` as index
review evidence. It does not infer that generated prose is a replacement for
the human-authored safety and architecture sections around the generated map.
