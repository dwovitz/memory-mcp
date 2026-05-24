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
- Docker/server deployment model for memory service operation.

This repo does not own:

- product-level assistant orchestration (`ai-os` owns that);
- local coding execution (`dark-factory` owns that);
- finance-domain reconciliation behavior (`personal-finance-os` owns that);
- raw source-of-truth project docs for other repos;
- storage decisions made without deployment-target analysis.

## Runtime Model

| Layer | Responsibility |
|---|---|
| MCP interface | Tool surface consumed by Claude, Codex, and local agents. |
| Memory retrieval | Context packet construction and relevance filtering. |
| Storage | Durable persistence for memories and embeddings. |
| Scope model | Workspace, project, repo, component, and sensitivity routing. |
| Entity graph | Structured entities and relationships where applicable. |
| Docker/runtime | Local or server-capable deployment and persistence. |

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

## AI Index Maintenance

Update `AI_INDEX.md`, this file, and the relevant `AGENTS.md` sections when MCP tool contracts, storage model, retrieval/context behavior, scope semantics, deployment assumptions, graph behavior, or safety policies change.
