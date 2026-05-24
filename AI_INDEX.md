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

## Critical Concepts

- Memory is a durable context layer for multiple harnesses, not a provider-specific feature.
- Project memory and personal memory should remain distinguishable.
- Retrieval should reduce token usage by surfacing relevant context packets before source reads.
- SQLite should not be assumed as the right scalable/server default; storage should be evaluated against deployment target.
- Memory should store compact facts, decisions, rules, commands, constraints, and project context — not raw transcripts, secrets, or sensitive data.
- Use the smallest meaningful validation loop for the change; do not default to expensive full-repo validation when a targeted check proves the contract.
- AI index updates are part of story closeout when navigation, commands, contracts, architecture, MCP behavior, storage/retrieval behavior, or generated-file boundaries change.

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
