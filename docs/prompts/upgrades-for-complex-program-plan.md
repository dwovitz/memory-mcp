# Upgrades For Complex Program Support

Plan file for making `memory-mcp` genuinely useful against a large, multi-repo,
event-driven program. The reference target is `ucx-root` — a ~9-application
healthcare case-management workspace mixing .NET services, a React SPA, Kafka
event contracts, and a shared gravity library.

## Executive Summary

`memory-mcp` already has the right *skeleton* for a complex program: a
lifecycle-aware memory store, JSONB-backed hierarchical scopes
(`global → workspace → project → component → topic`), an optional generic
`scope_path`, hybrid retrieval over structured filters + PostgreSQL full-text
ranking, token-budgeted context packet synthesis, pruning, and a clean MCP
tool surface. It also ships a provider-neutral auth/audit layer and a
cache-versioning protocol that coding clients can use to avoid redundant reads.

What it does *not* yet do well enough for a codebase like `ucx-root`:

- **No working semantic retrieval.** The `embedding` column and pgvector
  extension are present but the pipeline is explicitly scaffolded only
  (`vector_search_plan` returns `status="scaffold_only"`, `search_memories`
  raises `NotImplementedError` when `query_embedding` is passed). For a
  cross-repo program with many near-synonyms (Kafka/event/topic/observer,
  case/request/RFS, reviewer/MD/nurse), lexical FTS alone misses recall.
- **Entity graph is underused.** `Entity` and `Relationship` tables exist with
  typed links, but no MCP tool exposes graph traversal, entity linking, or
  relationship-aware retrieval. A complex program needs "which services
  consume `UserProfileConfigurationUpdated`", "which UI features call the
  Request Routing API", "which entities own this file" — that is a graph
  query, not a text search.
- **Hierarchy is four layers with a generic escape hatch.** Classic scope is
  `workspace → project → component → topic`. `ucx-root` needs at least one
  more first-class layer (repo), and the `scope_path` list-based approach
  requires the client to construct ordered strings like `"repo:UCX.UI"`. That
  is workable but places the schema burden on every caller.
- **No ingestion path for a large existing repo.** There is `scripts/seed_data.py`
  for synthetic personal-memory seeds, but nothing that turns an existing
  workspace (READMEs, ADRs, mermaid diagrams, APIM mappings, Kafka contracts,
  CLAUDE.md, code patterns rules) into memories. A human typing `add_memory`
  calls by hand will never load nine-service context.
- **No code-to-memory linking.** A `project_fact` memory cannot cite a file
  path, a symbol, a commit SHA, or a Kafka topic/message type in a structured
  way that survives renames. The knowledge-graph-style `code-review-graph`
  workflow hinted at in `memory-mcp/CLAUDE.md` is the sibling capability —
  memory-mcp currently has no equivalent.
- **Context packet synthesis is keyword-driven.** `PROJECT_CONTEXT_REQUEST_TERMS`
  and `BROADER_PROJECT_CONTEXT_TERMS` are hard-coded word lists. A request like
  "why isn't the SSL rule flowing into next-work-item?" would miss the routing
  branch heuristics entirely.
- **No multi-repo awareness at the workspace level.** `ucx-root` is a monorepo
  directory of independent git repos (UCX.UI, Ucx.CaseDetails,
  Ucx.RequestRouting, ucx.messages, evicore.gravity.common, etc.). There is no
  native `repo` scope, no cross-repo event-contract memory type, and no tool
  to ask "given a change in ucx.messages event X, what memory do consumers
  store?".
- **Retrieval precision over a large store is unmeasured.** The benchmark
  harness exists but its cases are personal-memory-shaped (shows, medications,
  the memory-mcp repo itself). There is no benchmark that proves retrieval
  stays precise when the store holds hundreds of cross-service facts.

### Fit Verdict

Usable today for single-repo coding context and personal-memory demos. **Not
yet a good fit for a nine-service, multi-repo, event-driven program** without
the upgrades listed below. The architecture is extensible enough that these
upgrades are incremental, not a rewrite.

## Target Program Profile (`ucx-root`)

Captured here so reviewers do not have to re-derive it.

| Dimension | ucx-root value | Memory-mcp implication |
| --- | --- | --- |
| Repos in workspace | 10+ sibling git repos under one workspace | Need first-class `repo` scope or reliable `scope_path` usage |
| Services | 9 .NET microservices + 2 React SPAs + 2 shared libraries | Each is a natural `project` (and each has internal `component`s) |
| Cross-service contracts | Kafka events in `ucx.messages`, shared framework `evicore.gravity.common` | Need a stable way to store "event X is produced by A, consumed by B, C" |
| Storage per service | CosmosDB per service | Storage facts are per-project |
| Gateway | Azure API Management with terraform-defined routes | `apim.tf` → controller mapping is a recurring fact worth memorizing |
| Frontend | React + React Query with ~24 feature folders and ~8 API domains | Feature ↔ API domain mapping is a graph-shaped fact |
| AI tooling | Rules in `ucx-ai/rules/*.mdc`, skills in `ucx-ai/skills/`, mermaid diagrams with file-path references | Durable guidance that should be ingested into memory |
| Scope surface | workspace (`ucx-root`) → repo → service area → layer (Api/Application/Domain/Infrastructure/Observer) → feature | Five practical layers; current classic scope covers three cleanly |
| File count (rough) | UCX.UI 835, Ucx.CaseDetails 468, Ucx.RequestRouting 304, plus seven more repos, totaling 2,000+ files | Retrieval must scale to hundreds of project/component memories |
| Event-driven | All backend services are event-sourced (Kafka → Observer → CosmosDB → API) | Retrieval should distinguish "producer", "consumer", "handler", "state projection" |

## Affected Areas Of `memory-mcp`

| Area | File(s) | Why it is touched |
| --- | --- | --- |
| Schema / migrations | `migrations/versions/*.py`, `src/memory_mcp/models/schema.py` | New memory types, new scope fields, embedding dimension, code-citation columns |
| Hierarchy and scope helpers | `src/memory_mcp/scopes.py` | Add `repo` scope, code-citation normalization, scope aliases |
| Retrieval | `src/memory_mcp/retrieval/service.py` | Vector search, relationship traversal, repo-scoped hierarchy, cross-scope joins |
| Context synthesis | `src/memory_mcp/services/context_synthesis.py` | Classifier upgrade, event-flow awareness, entity-graph expansion, repo-aware fallback |
| MCP tool surface | `src/memory_mcp/mcp_tools/server.py` | New tools (graph traversal, entity upsert/link, ingest, workspace inventory, cross-service flow), new parameters (`repo`, `code_citations`, `embedding`) |
| Ingestion | `scripts/` (new: `ingest_workspace.py`, `ingest_code_graph.py`), `src/memory_mcp/ingest/` (new package) | First-run population from a target workspace |
| Tests and benchmarks | `tests/`, `benchmarks/cases.json`, `benchmarks/prompts/` | New multi-repo benchmark cases, retrieval precision tracking |
| Docs | `docs/ARCHITECTURE.md`, `docs/AGENT_WORKFLOW.md`, `README.md` | Document new scope, tools, ingestion, and benchmarks |

## Recommended Upgrades (Prioritized)

Priority is read "impact for complex-program use / effort". Items lower in the
list depend on or build on items higher up, so execute top-down unless
otherwise noted.

### P0 — Workspace Ingestion Pipeline

**Rationale.** Nothing else matters until a workspace's durable facts are
actually *in* the database. Today, the only population paths are `add_memory`
calls from an agent and `scripts/seed_data.py` (synthetic). For a nine-service
program, we need a repeatable, idempotent ingestion script that reads an
allowlisted set of sources and emits memories with provenance.

**Scope of work.**

- New `src/memory_mcp/ingest/` package with:
  - `sources.py` — configurable source registry (README, ARCHITECTURE, ADRs,
    mermaid diagrams, rule/skill `.md`/`.mdc`, `apim.tf` files, `catalog-info.yaml`).
  - `parser.py` — pluggable extractors: markdown section → memory, mermaid
    node table → entities+relationships, apim terraform operations →
    endpoint facts, kafka contract classes → event entities.
  - `writer.py` — thin wrapper over `MemoryService` that upserts with a stable
    `metadata.ingest_key` so reruns supersede instead of duplicating.
- New `scripts/ingest_workspace.py` driven by a small YAML manifest
  (`ingest.manifest.yaml`) the operator points at a workspace root.
- New MCP tool `ingest_workspace_inventory` (read-only) that reports what
  would be ingested without writing, so clients can dry-run.

**Tradeoffs.** Parsers are source-format-specific and will need maintenance.
Start with three extractors (markdown headings, mermaid key-file-reference
tables, apim terraform route blocks) and leave the rest behind a `strict=false`
flag. Resist the temptation to extract from arbitrary code files; that is the
job of the code-graph (P3).

**Quick win inside this track.** A single-file script that walks
`ucx-ai/rules/*.mdc` and `ucx-ai/mermaid-diagrams/*.md` and writes one memory
per heading, scoped `workspace=ucx-root`. That alone populates enough
workspace-level facts to make `get_context_packet` useful against ucx-root on
day one.

### P0 — Add `repo` As A First-Class Scope Layer

**Rationale.** `ucx-root` is a workspace of independent git repositories. The
current classic hierarchy (`workspace → project → component`) treats "project"
as "repo". That collapses if you ever have multiple repos under one project,
but more importantly, for ucx-root the natural fact *shape* is:

> workspace=ucx-root, repo=UCX.UI, component=api, topic=requestRouting.

Today you must either squeeze "repo" into "project" and then drop "component",
or switch to `scope_path`. The generic `scope_path` works but every caller
pays the cost of constructing ordered strings.

**Scope of work.**

- `src/memory_mcp/scopes.py` — add `REPO_MEMORY_SCOPE` and `REPO_KEY`, extend
  `with_memory_scope`, `_hierarchy_layers`, and `scope_path_layers` to
  support `repo` between `project` and `component`.
- `src/memory_mcp/mcp_tools/server.py` — add `repo` parameter to `add_memory`,
  `supersede_memory`, `search_memory`, `get_context_packet`, `list_preferences`,
  `summarize_domain_profile`; validate, route through `_scoped_applies_to`.
- Migration: no schema change required — it lives inside `applies_to` JSONB —
  but add a composite functional GIN index for
  `(applies_to->>'workspace', applies_to->>'repo', applies_to->>'project')`
  so hierarchical filters stay fast as the store grows.
- Keep backward compatibility: when callers pass `project` without `repo`,
  retrieval treats `repo == project` implicitly so existing memories still
  match.

**Tradeoffs.** Five layers (global/workspace/repo/project/component) is getting
close to `scope_path` territory. Stop here — do not keep adding layers. If the
caller needs module/branch/feature distinctions, they should keep using
`scope_path`.

### P0 — Semantic (Vector) Retrieval

**Rationale.** Full-text rank over PostgreSQL `to_tsvector` misses synonyms and
paraphrase. In ucx-root, "event" vs "message" vs "kafka topic" vs "domain
event" refer to the same concept. "Request" vs "case" vs "RFS" overlap.
"Reviewer" vs "MD" vs "Nurse" overlap. Lexical FTS alone will produce high
precision but low recall on realistic agent queries.

The pgvector extension is already enabled and there is a placeholder
`embedding` column. The `VectorSearchPlan` dataclass advertises `hnsw` as the
intended index. This is the most expected upgrade.

**Scope of work.**

- Pick an embedding model and dimension. Recommend a local model so the stack
  stays "local-first" as advertised in README. Candidates:
  `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU-friendly) or
  `bge-small-en` (384-dim). The exact choice is not load-bearing for the plan.
- New `src/memory_mcp/embeddings/` package:
  - `provider.py` — interface plus a default local implementation.
  - `service.py` — batches text → embedding, caches by content hash, writes
    to `memories.embedding`.
- Migration: set embedding dimension, add HNSW index with `vector_cosine_ops`
  on `memories.embedding WHERE status = 'active'`.
- Retrieval: in `HybridRetrievalService.search_memories`, when `text_query`
  is present, compute `query_embedding` lazily and combine with existing
  `text_rank`, `confidence`, `recency_score`. Exact blending weights are a
  knob — start with `0.35*vector + 0.35*text + 0.2*confidence + 0.1*recency`
  and tune via benchmarks.
- Backfill: new `scripts/backfill_embeddings.py` iterates active memories that
  have `embedding IS NULL`.
- Config: `MEMORY_MCP_EMBEDDING_ENABLED`, `MEMORY_MCP_EMBEDDING_MODEL`,
  `MEMORY_MCP_EMBEDDING_DIMENSIONS`. Default to disabled until the model is
  present, and fall back cleanly to FTS-only retrieval if the provider is
  missing.

**Tradeoffs.** Running a local embedding model adds a Python dependency and
CPU cost per write. For the local trusted-stdio target this is acceptable.
For a future hosted mode, add a remote-provider variant of the interface.

**Quick win.** Even without re-ranking, using vector cosine *only* to
**re-expand** the FTS candidate set (pull top 50 by FTS, rerank by vector) is a
one-query change and captures most of the recall lift.

### P1 — Expose The Entity Graph (Relationship Traversal)

**Rationale.** `entities` and `relationships` tables exist and are populated by
seed data, but the MCP tool surface does not let a caller walk them. For
ucx-root, a huge share of "context for this task" is relationship-shaped:

- "What services produce and consume `UserProfileConfigurationUpdated`?"
- "Which UCX.UI feature folders call `Ucx.RequestRouting.Api`?"
- "What event families are handled by `Ucx.CaseDetails.Observer`?"
- "Which stores feed data into `Case Drawer`?"

These are natural for the `Relationship` table (source_entity, target_entity,
relationship_type) and unnatural for free-text retrieval.

**Scope of work.**

- New MCP tools:
  - `upsert_entity(entity_type, name, aliases?, attributes?, applies_to?)`
    (already possible via repositories but not via MCP).
  - `link_entities(source_id, target_id, relationship_type, description?, evidence?, applies_to?)`.
  - `search_entities(text_query?, entity_types?, scope?, limit?)`.
  - `traverse_entity_graph(start_entity_id, relationship_types?, direction?,
    max_depth=2, include_memories=true, limit=20)` — breadth-first walk that
    returns the visited subgraph plus attached memories.
  - `get_related_memories(entity_id, relationship_types?, direction?)` — thin
    helper that fetches memories whose `entity_id` is the start entity or a
    direct neighbor.
- Retrieval: extend `HybridRetrievalService` with graph helpers. Use
  PostgreSQL recursive CTEs for traversal rather than N+1 queries.
- Context synthesis: when the request classification names concrete entities
  (service names, event names, feature names), pull a bounded neighborhood
  into the packet alongside the text-ranked results.

**Tradeoffs.** Graph traversal defaults must be bounded (`max_depth`, per-level
cap) to avoid unbounded fan-out. Start with max_depth=2 and a cap of 50 nodes.

### P1 — Code Citations On Memories

**Rationale.** In a large codebase, a `project_fact` like "Request routing
decides reviewer based on specialty and state license" is far more useful if
it cites `Ucx.RequestRouting/Application/Services/Implementation/*.cs` and
the controller line number than if it is naked prose. Citations also make
memory verifiable (agents can spot-check before trusting) and make pruning
smarter (supersede when the cited file is deleted or renamed).

**Scope of work.**

- Schema: add JSONB column `code_citations` to `memories`, shape
  `[{ "repo": "...", "path": "...", "lines": [start, end]?, "symbol": "...",
    "commit": "..."?, "kind": "file|symbol|event|endpoint" }]`. Add GIN index.
- Validator in `mcp_tools/server.py`: bound citation count (`MAX_CITATIONS = 20`),
  path length, prevent absolute filesystem paths outside the workspace.
- `add_memory` / `supersede_memory`: accept `code_citations` list.
- `search_memory`: optional `cited_path` filter that matches memories touching
  a given path prefix.
- Pruning: a new rule that flags citations pointing at files that no longer
  exist — does NOT auto-prune, just records in `pruning_log` and reduces
  confidence.

**Tradeoffs.** We are not building a full code graph (that is P3). Citations
are a *soft* link — they survive rename (fuzzy match) but must not be trusted
blindly.

### P1 — Upgrade Request Classifier Beyond Keyword Lists

**Rationale.** `PROJECT_CONTEXT_REQUEST_TERMS` and
`BROADER_PROJECT_CONTEXT_TERMS` in `context_synthesis.py` are hard-coded word
lists. A ucx-root caller asking "why isn't the next-work-item request pulling
the updated SSL rule?" would trigger only weak matches. The classifier should
extract *entities* and *memory-type hints* from the request, not just detect
broad domains.

**Scope of work.**

- Refactor `RequestClassification` to also expose `matched_entities`,
  `hinted_memory_types`, and `hinted_repos`.
- Implement a two-pass classifier:
  1. Lightweight lexical pass (current behavior) to set domain.
  2. Entity-matching pass: use `search_entities` with the request text against
     the entity store, keep hits above a confidence threshold.
- Once embeddings exist (P0 vector work), also compute a request embedding
  and pull top-k nearest entities.
- Feed matched entities into retrieval as `entity_id` hints and into graph
  traversal (P1) for related memory expansion.

**Tradeoffs.** Entity matching needs a populated entity store (depends on
ingestion, P0). Until ingestion exists, this upgrade is mostly dead weight, so
sequence it after ingestion is producing entities.

### P2 — Event-Flow And Cross-Service Memory Types

**Rationale.** Event-sourced programs like ucx-root have durable facts of the
form "event E (defined in repo X) is produced by service A on trigger T, and
consumed by services B, C, D, which project it into stores S_B, S_C, S_D".
Storing those as generic `project_fact` rows loses the structure. Retrieval
cannot ask "for this event, show me all consumers".

**Scope of work.**

- Two new memory types recognized by retrieval classifiers and the pruning
  service: `event_contract`, `service_dependency`.
- Recommend (but do not enforce) a canonical metadata shape:
  ```json
  {
    "event_name": "UserProfileConfigurationUpdated",
    "producers": [{"service": "UCX.ConfigurationService", "file": "..."}],
    "consumers": [{"service": "Ucx.RequestRouting", "handler": "..."}],
    "schema_repo": "ucx.messages",
    "schema_symbol": "UserProfileConfigurationUpdatedEvent"
  }
  ```
- New MCP tool `get_event_flow(event_name)` that returns producers, consumers,
  handlers, and cited files in one call.
- Context packet: when the request references an event name present in the
  store, include its flow summary in `facts`.

**Tradeoffs.** This is a convention, not a new schema. Keep it in JSONB so
early experimentation is cheap. Promote to columns only if it stabilizes.

### P2 — Context Packet Quality Signals For Multi-Repo

**Rationale.** Today's packet quality signals (`weak`/`strong`, warnings,
fallback attempts) treat the store as single-project. In multi-repo, "weak
context" should be refined:

- Weak because no memories match this *repo*.
- Weak because no memories match this *event* or *entity*.
- Strong for project context but no component-level detail.

**Scope of work.**

- Extend `ContextPacket.diagnostics` with `matched_repos`, `matched_entities`,
  `matched_event_names`, and per-layer counts.
- `suggested_next_action` should branch on what's missing: "run
  `get_event_flow` first" / "run `traverse_entity_graph` first" / the current
  `verify_narrowly` / `mark_weak_context` advice.
- Update tests in `tests/services/test_context_synthesis.py` for the new
  diagnostics.

### P2 — Ingestion Of Code Graph Signals

**Rationale.** Memory-mcp intentionally is not a code graph (per GOALS.md).
But it can *consume* signals from one. The sibling project's CLAUDE.md
already references a `code-review-graph` MCP. Memory-mcp should be able to
receive high-signal graph outputs (module boundaries, high-fan-in nodes,
orphaned tests) as memories without re-implementing the graph.

**Scope of work.**

- New MCP tool `import_code_graph_summary(summary_json, scope...)` that
  accepts a bounded, schema-validated payload from another tool and writes
  it as `project_fact`/`architecture_decision` memories with citations.
- Schema-validate the payload (size cap, required fields), reject unknown
  keys.
- Integration tests that feed a synthetic payload and verify memories are
  written idempotently on rerun.

**Tradeoffs.** This is glue, not a dependency — if no upstream graph is
available, callers simply never call the tool. Keep the accepted schema tiny
and versioned.

### P2 — Scale And Retrieval-Precision Benchmarks For Multi-Repo

**Rationale.** The existing benchmark harness (`benchmarks/`) validates
personal-memory and self-referential packets. There is no evidence that
retrieval stays precise when the store contains hundreds of cross-service
facts. Before committing to the embedding/graph upgrades, we need a harness
that measures precision@k, recall@k, and packet token budgets on a realistic
multi-repo corpus.

**Scope of work.**

- Add `benchmarks/multi_repo_cases.json` with at least 40 realistic agent
  queries against a ucx-root-shaped synthetic corpus (no real content,
  just realistic *shapes* — service names, event names, feature names).
- Add `benchmarks/run_multi_repo_benchmarks.py` that:
  - Seeds a fresh DB with the synthetic corpus.
  - Runs each case, records returned memory IDs and rendered packet tokens.
  - Compares to gold IDs per case.
  - Emits `benchmarks/results/multi-repo-YYYY-MM-DD.json`.
- Thresholds: `precision@8 ≥ 0.7`, `recall@8 ≥ 0.6`, packet median tokens
  within budget. These are starting numbers; tune against the first real run.

**Tradeoffs.** Synthetic corpus generation is real work. Keep the generator
deterministic (seeded RNG) so benchmarks are reproducible.

### P3 — Optional Client Hook Pack For UCX-Style Workspaces

**Rationale.** `ucx-root` already has `ucx-ai/skills/` and `.claude/agents/`.
Memory-mcp should ship an opinionated companion pack — not required, just
available — that wires ingestion, retrieval, and refresh into an existing
Claude Code / Cursor / Copilot workspace. Lowers the integration cost for
other multi-repo consumers.

**Scope of work.**

- `client-setups/ucx-workspace/` folder with:
  - A manifest template (`ingest.manifest.yaml` populated for ucx-root).
  - An `AGENTS.md` describing the memory-first workflow (uses the existing
    `AGENT_WORKFLOW.md` as source material).
  - A simple pre-session hook script that calls `get_memory_cache_state` and
    warns when the store is empty.
- Clearly labeled as "reference, not required".

**Tradeoffs.** This is documentation + scaffolding. Low engineering risk, but
scope creep is easy — hold the line at templates and docs only.

### P3 — Hosted / Remote Mode Hardening

**Rationale.** Out of scope for the ucx-root integration but worth noting: the
auth/audit layer already supports `MEMORY_MCP_AUTH_MODE=remote`. A production
multi-user deployment would need per-tenant data isolation, rate limits, and
backups. Defer until a real remote consumer asks for it.

## Quick Wins (under ~1 day each)

These can be picked off independently from the main roadmap and provide
immediate value against ucx-root.

1. **Markdown ingest of `ucx-ai/rules/*.mdc` and mermaid diagrams.** A single
   script that writes one memory per heading, scoped `workspace=ucx-root`.
   No schema changes. Unblocks useful `get_context_packet` calls.
2. **Add `repo` parameter to existing MCP tools** as an *alias* for `project`
   (validated but not yet plumbed through retrieval). Lets callers adopt the
   new vocabulary before the full P0 hierarchy change lands.
3. **Add `cited_path` filter to `search_memory`.** Even before the
   `code_citations` column exists, match against `applies_to.cited_paths` so
   clients can start tagging memories with paths today.
4. **Expose `search_entities` as an MCP tool.** The retrieval service already
   implements it; only the MCP wrapper is missing. Unblocks any caller that
   knows an entity name.
5. **Document the multi-repo scope_path convention.** Pick canonical part
   prefixes (`workspace:`, `repo:`, `project:`, `component:`, `topic:`,
   `branch:`, `feature:`) and commit them to `docs/ARCHITECTURE.md`. Costs
   nothing, prevents client drift.
6. **Refuse `add_memory` for obvious secrets.** Regex-level check on `content`
   for AWS keys, bearer tokens, Azure connection strings. Rejects (not warns)
   when matched. Cheap safety win for any real workspace.

## Larger Architectural Changes

Sequenced for readability. Depends lines show hard prerequisites.

| Change | Depends | Rough size |
| --- | --- | --- |
| Workspace ingestion pipeline (P0) | — | ~5–8 days |
| `repo` as first-class scope (P0) | — | ~2–3 days |
| Embedding pipeline + HNSW (P0) | — | ~4–6 days |
| Code citations on memories (P1) | repo scope | ~3 days |
| Entity graph traversal MCP tools (P1) | — (uses existing tables) | ~4 days |
| Upgraded classifier (P1) | ingestion, entities | ~2–3 days |
| Event-flow memory types (P2) | ingestion, graph | ~3 days |
| Multi-repo packet diagnostics (P2) | classifier | ~1–2 days |
| Code-graph import tool (P2) | code citations | ~2 days |
| Multi-repo benchmark harness (P2) | most of the above | ~4 days |
| Client hook pack (P3) | ingestion | ~2 days |

## Risks And Open Questions

1. **Embedding model choice.** The plan assumes a local CPU-friendly model to
   keep the "local-first" promise. If that is not acceptable (latency or
   quality), the embedding provider interface supports a remote variant, but
   that changes the threat model — per README, the store may contain
   sensitive facts. Decide before building the provider interface.
2. **Source of truth between memory-mcp and a code graph.** If a sibling
   `code-review-graph` MCP is available (the host's CLAUDE.md for
   memory-mcp references one), boundaries should be: graph owns derivable
   structural facts (call graphs, imports, test coverage); memory-mcp owns
   decisions, conventions, and durable commentary with citations into the
   graph. Document this boundary explicitly.
3. **Repo scope vs project scope backward compatibility.** Existing memories
   have `project` but not `repo`. The plan's "treat `repo == project`
   implicitly when `repo` is absent" rule must be validated with tests on the
   seed data before shipping.
4. **Ingestion idempotency key shape.** `metadata.ingest_key` must be stable
   across reformatting. Proposed key: hash of (source path, heading path,
   heading text). Confirm this does not churn on trivial doc edits.
5. **How much should memory-mcp *parse* vs accept as input?** Resist the urge
   to parse code. Parse only documentation and declarative config (mermaid
   tables, apim.tf, README headings). For code-derived facts, rely on the
   `import_code_graph_summary` tool.
6. **Retrieval cost with HNSW at scale.** HNSW is fast but not free. With a
   few thousand memories this is not an issue; validate at ~50k before
   removing the FTS-only fallback.

## Questions For The User

Before implementation, please confirm:

1. **Scope of the first integration.** Are we aiming to ingest all nine
   ucx-root repos, or start with a single service (say, `Ucx.RequestRouting`)
   plus the shared `ucx-ai/` guidance?
2. **Embedding constraints.** Is a local embedding model (CPU, 384-dim)
   acceptable, or should the design assume a remote API from the start?
3. **Code graph coexistence.** Does a code-review-graph MCP actually run
   alongside memory-mcp in your workflow? If yes, the `import_code_graph_summary`
   tool (P2) jumps in priority.
4. **Hosted mode timing.** Is there a near-term plan to run memory-mcp for
   more than one user? That would change auth/audit priorities.
5. **Breaking changes tolerance.** `repo` as a first-class scope is additive,
   not breaking, if we default `repo = project`. Is that acceptable, or do
   you want to keep the current 4-layer hierarchy and push everything to
   `scope_path` instead?
6. **Personal-memory features.** The existing personal-memory tools
   (`list_medications_for_person`, `list_liked_media`) are orthogonal to
   complex-program support. Do you want them retained, deprecated, or moved
   behind a flag?

## Task Breakdown (Optional, For Estimation)

Suggested discrete work items, grouped by upgrade. Each is meant to be a
single reviewable PR.

1. **Ingestion Phase 1** — Add `src/memory_mcp/ingest/` skeleton, markdown
   heading parser, `scripts/ingest_workspace.py` with dry-run flag, manifest
   schema. Acceptance: running against `ucx-ai/rules/*.mdc` produces one
   memory per heading, reruns are idempotent.
2. **Repo scope — schema and helpers** — Extend `scopes.py`, update
   `with_memory_scope`, `_hierarchy_layers`, `scope_path_layers`; add tests.
   No tool-surface change yet. Acceptance: existing retrieval tests pass
   unchanged; new repo-scoped tests pass.
3. **Repo scope — MCP tool surface** — Add `repo` parameter across all seven
   affected tools, preserve `project`-only backward compat. Acceptance: hand
   integration test exercising every tool with and without `repo`.
4. **Embedding provider interface** — Add `src/memory_mcp/embeddings/` with
   provider protocol and a local sentence-transformers implementation behind
   a config flag. Acceptance: unit tests with a stub provider.
5. **HNSW index migration** — Add Alembic migration that sets dimension and
   creates the HNSW index. Acceptance: migration runs on an empty DB and on
   a seeded DB without data loss.
6. **Hybrid retrieval with vector re-rank** — In `search_memories`, compute
   query embedding (when FTS candidate set is non-empty) and blend the
   scores. Acceptance: benchmark precision@8 improves on multi-repo cases.
7. **Code citations column** — Schema migration, validator, tool parameter,
   `cited_path` filter. Acceptance: round-trip test via `add_memory` +
   `search_memory`.
8. **Entity graph MCP tools** — `upsert_entity`, `link_entities`,
   `search_entities`, `traverse_entity_graph`, `get_related_memories`.
   Acceptance: BFS traversal test with depth bounds.
9. **Classifier upgrade** — Two-pass classifier using entities and embeddings;
   integrate into `ContextSynthesisService`. Acceptance: packet diagnostics
   expose matched entities; benchmark precision holds or improves.
10. **Event-flow memory type + `get_event_flow` tool** — Convention + tool +
    docs. Acceptance: round-trip against a synthetic event corpus.
11. **Multi-repo benchmark harness** — Synthetic corpus generator, run
    script, thresholds, results directory. Acceptance: harness runs on an
    ephemeral DB and writes a results file.
12. **Docs refresh** — Update `ARCHITECTURE.md`, `AGENT_WORKFLOW.md`,
    `README.md` to describe new scope, tools, ingestion, and benchmarks.

---

## Implementation Log

### Session 2026-05-06 — Quick Wins + Setup Prompts (branch: feat/complex-program-support)

**Decisions made (answers to "Questions For The User" above)**

1. Scope of first integration — Generic only. No ucx-root-specific wiring.
   memory-mcp improvements are repo-agnostic.
2. Embedding constraints — Local CPU model acceptable
   (sentence-transformers/all-MiniLM-L6-v2 or bge-small-en, 384-dim).
3. Code graph coexistence — Not answered yet. P2 item unchanged.
4. Hosted mode timing — Deferred. P3 unchanged.
5. Breaking changes tolerance — `repo = project` implicit alias is acceptable.
6. Personal-memory features — Retained as-is.

**Completed quick wins**

- ✅ QW2 — `repo` parameter added to `add_memory`, `supersede_memory`,
  `search_memory`, `get_context_packet`, `list_preferences`,
  `summarize_domain_profile`. Aliases to `project` when project is absent.
  `REPO_KEY = "repo"` added to `scopes.py`. Value stored in `applies_to.repo`.
- ✅ QW4 — `search_entities` exposed as MCP tool (backed by existing
  `HybridRetrievalService.search_entities`). Accepts query, entity_types,
  workspace, repo, project, scope, limit.
- ✅ QW5 — Canonical `scope_path` prefixes documented in `docs/ARCHITECTURE.md`
  with a table and usage example.
- ✅ QW6 — Secrets guard added to `add_memory` and `supersede_memory`. Rejects
  content matching AWS access keys, private key headers, Bearer tokens, and
  Azure AccountKey strings.

**Not yet done (deferred)**

- ⬜ QW1 — Markdown ingest script for workspace docs. Deferred (needs ingestion
  package from P0 track first).
- ⬜ QW3 — `cited_path` filter on `search_memory`. Deferred (needs
  `code_citations` column from P1 code-citations track first).

**New deliverables (not in original plan)**

- `client-setups/setup-new-repo/SETUP_PROMPT.md` — agent prompt for new repos.
- `client-setups/setup-existing-repo/SETUP_PROMPT.md` — agent prompt for
  existing repos (reads README, ADRs, CLAUDE.md, docker-compose, etc.).
- `docs/plan/implement-quick-wins-prompt.md` — reproducible implementation
  prompt for these changes.
- `client-setups/README.md` updated to surface setup prompts as the first step.
- `docs/ARCHITECTURE.md` updated: new tools in surface table, `repo` parameter
  section, canonical scope_path prefix table.

---

**Status:** In progress. Quick wins delivered on branch `feat/complex-program-support`.
Next priority: P0 — `repo` as first-class retrieval scope, semantic (vector)
retrieval, workspace ingestion pipeline. See task breakdown items 1–6 above.
