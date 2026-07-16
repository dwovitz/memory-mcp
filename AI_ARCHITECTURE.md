# AI Architecture

## Architectural Intent

`memory-mcp` is a durable memory/context service for AI agents. It should help Claude, Codex, local models, and future orchestration layers retrieve compact, relevant context before consuming large source or chat histories.

The system should remain provider-neutral and usable across projects, repos, and harnesses.

## Boundaries

This repo owns:

- MCP memory service behavior;
- durable memory storage and retrieval;
- scope-aware context packets;
- project and component memory organization;
- entity/relationship memory where implemented;
- memory safety rules and sensitive-data handling;
- Docker/server deployment model for memory service operation;
- AI-facing navigation/index policy for this memory service repo.

This repo does not own:

- product-level assistant orchestration (`ai-os` owns that);
- local coding execution (`dark-factory` owns that);
- finance-domain reconciliation behavior (`personal-finance-os` owns that);
- raw source-of-truth project docs for other repos;
- storage decisions made without deployment-target analysis;
- replacing source inspection with stale generated summaries.

## Runtime Model

| Layer | Responsibility |
|---|---|
| MCP interface | Tool surface consumed by Claude, Codex, and local agents. |
| Memory retrieval | Context packet construction and relevance filtering. |
| Storage | Durable persistence for memories and embeddings. |
| Scope model | Workspace, project, repo, component, and sensitivity routing. |
| Entity graph | Structured entities and relationships where applicable. |
| Docker/runtime | Local or server-capable deployment and persistence. |

## Current Component Map

| Component | Primary paths | Boundary to preserve |
|---|---|---|
| MCP interface | `src/memory_mcp/mcp_tools/server.py`, `src/memory_mcp/main.py` | Tool inputs/outputs remain bounded; server-side policy remains authoritative. |
| Auth and grants | `src/memory_mcp/auth/` | Trusted local and authenticated remote modes must remain explicit; clients do not grant themselves capabilities. |
| Storage lifecycle | `src/memory_mcp/models/`, `src/memory_mcp/repositories/`, `migrations/` | PostgreSQL schema evolution is migration-backed; provenance and lifecycle state must survive changes. |
| Retrieval/context | `src/memory_mcp/retrieval/`, `src/memory_mcp/services/context_synthesis.py` | Packets are bounded, scope-aware, sensitivity-filtered orientation—not unbounded source dumps. |
| Ingestion/projection | `src/memory_mcp/ingest/`, `scripts/ingest_wiki.py` | The file wiki is canonical; stored memory is a provenance-stamped projection. |
| Auto-capture | `hooks/`, `src/memory_mcp/mcp_tools/server.py`, `src/memory_mcp/distiller/`, `src/memory_mcp/repositories/staging.py` | Enqueue is an authorized, bounded write; raw observations are staged before governed promotion and must not block client hooks. Promoted claims are private and retain server-validated, claim-specific staging provenance. |
| Deployment | `Dockerfile`, `docker-compose.yml`, `.env.example` | PostgreSQL is the shared durable store; exposed modes require explicit security configuration. |
| Validation | `tests/`, `pytest`, `mypy`, `scripts/ai_index_check.py` | Focused tests establish local behavior; full outer-harness gates still apply before publication. |

## AI Index Model

AI-facing index files are part of the repo contract. They provide navigation and safety context before source edits, especially when connector search is unreliable.

The index model has four layers:

| Layer | Responsibility |
|---|---|
| `AGENTS.md` | Shared operating rules, startup order, closeout policy, graph/context expectations, and safety boundaries. |
| `AI_INDEX.md` | Compact repo map, main entrypoints, common starting paths, graph/context usage, source-of-truth files, and non-editable/generated boundaries. |
| `AI_ARCHITECTURE.md` | Durable memory service architecture, storage/retrieval boundaries, scope model, context packet behavior, and MCP contracts. |
| `.ai/index.json` | Machine-readable generated index for automation and checks. |

Automation may refresh generated regions and machine-readable data. It must not blindly overwrite human-authored architecture intent, safety policy, or ownership boundaries.

## Strategic Role

`memory-mcp` is the durable context layer across the AI project ecosystem:

| Repo | Relationship |
|---|---|
| `ai-os` | Uses memory for assistant/project continuity. |
| `dark-factory` | Uses memory for execution context and story/project facts. |
| `personal-finance-os` | Uses memory for non-sensitive project rules and workflow context, not raw finance data. |

## Design Principles

- Retrieval should reduce token usage and broad file reads.
- Memory entries should be compact, durable, and non-sensitive by default.
- Scopes should support personal, workspace, project, repo, and component context.
- Context packets should guide source-read policy.
- Storage must be evaluated against deployment target; do not assume SQLite is the long-term default for scalable/server operation.
- The service should be usable by Claude, Codex, and other harnesses without provider lock-in.
- Use scoped validation whenever it proves the changed contract; reserve full-suite validation for changes that require it.
- AI index files are navigation aids, not stale RAG substitutes.

## AI Index Maintenance

Update `AI_INDEX.md`, this file, `.ai/index.json`, and the relevant `AGENTS.md` sections when MCP tool contracts, storage model, retrieval/context behavior, scope semantics, deployment assumptions, graph behavior, safety policies, validation expectations, or generated-file boundaries change.

The closeout path should record whether the repo AI index was checked, whether updates were needed, which files changed, and the reason if no index update was needed.
