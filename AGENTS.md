# memory-mcp

PostgreSQL + pgvector memory service with MCP interface. Provides durable project memory across Claude and Codex sessions via Docker.

memory-mcp is a **retrieval/projection service**, not an unchecked runtime assistant. Every agent working in this repository must satisfy the issue readiness contract before beginning implementation.

Shared always-on policy — core working style, branch and validation workflow, memory retrieval and
write policy, routing and delegation, safety — is authored once in `ai-rules` and is not repeated
here. Read `ai-rules/rules/`. This file carries only what is specific to `memory-mcp`.

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

**Fail closed** (`ai-rules/rules/10-workflow.md`): if any check fails, stop, report the specific missing items, and do not proceed.

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

See `ai-rules/rules/30-routing.md`. `code-review-graph` is configured for this repo.

## Model Routing (Codex)

Tier selection and brief requirements are in `ai-rules/rules/30-routing.md`. This repo's
model/effort table:

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

See `.memory-mcp/outer-run.md` for the full table covering both Claude and Codex.

## Memory

Retrieval, caching, source-read policy, and write rules are in `ai-rules/rules/20-memory.md`.
Scope for this repo:

```text
workspace="ai"
project="memory-mcp"
repo="memory-mcp"       # narrows to this repo within the project
component="<subsystem when clear>"
```

Include `repo="memory-mcp"` in `add_memory` scope for finer routing.

## Knowledge Ingestion

A local file-based wiki is the **canonical** source of private human-readable knowledge. `memory-mcp` stores **projections** of it — searchable derived records with provenance (`metadata.source`), classified `private` by default. Treat the wiki as the source of truth; never make `memory-mcp` the canonical editor of wiki content, and do not hand-author memories that duplicate canonical wiki sections — run wiki ingestion instead (`scripts/ingest_wiki.py`, `memory_mcp.ingest.wiki.WikiIngestService`). Ingestion is idempotent: unchanged sections are skipped, changed sections supersede, and removed sections/files are archived. Wiki link structure is also projected deterministically into `wiki_document` entities and `references` relationships (provenance-stamped, same stale sweep) so retrieval can do bounded relationship expansion; never hand-author graph edges that duplicate wiki links. See [docs/wiki_ingestion.md](docs/wiki_ingestion.md) and [docs/retrieval.md](docs/retrieval.md).

<!-- secret-migrate:start -->
## Local secret management

Read `docs/secret-management.md` before running this repository. Use the generated `scripts/with-secrets` or `scripts/dev-up` launcher, and never
inspect or print secret values.
<!-- secret-migrate:end -->
