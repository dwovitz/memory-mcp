# Canonical Backlog

This file is the human-readable canonical backlog for `memory-mcp` implementation planning.

The repo-local backlog is the implementation source of truth for memory-MCP work. GitHub Issues should be created only when a story is selected for implementation or when a concrete bug/follow-up is discovered.

## Current source-of-truth policy

- New implementation stories are added here or to a dedicated markdown/CSV file under `backlog/`.
- Accepted architectural decisions should be captured in `docs/decisions/` when that decision-log structure exists.
- Selected stories should receive compact specs under `.ai/specs/` before coding when they need design detail.
- Design-heavy stories should receive design notes under `.ai/design/` before implementation.
- GitHub Issues are for implementation-ready selected stories, bugs, test failures, or concrete follow-ups.
- Existing GitHub Issues migrated into this file should be closed with a note that the canonical backlog now owns planning state.

## Immediate backlog sequence

### 1. Memory lifecycle and consolidation

| ID | Title | Priority | Status | Notes |
|---|---|---:|---|---|
| MMCP-001 | Implement scheduled Memory Dream consolidation worker | P0 | Backlog | Add an explicit consolidation pass inspired by Claude Code Auto Dream: review recent memory, merge duplicate or overlapping facts, resolve conflicts, prune stale/low-value entries, promote durable scoped memories, archive superseded detail, and write provenance/audit records. Must fit server-scalable PostgreSQL/pgvector architecture rather than local-only file cleanup. |
| MMCP-002 | Build CLI for memory-MCP | P1 | Backlog | Add a first-class CLI for creating, searching, inspecting, pruning, exporting, and administering memory through the shared authenticated memory-MCP service rather than through chat adapters only. Must support scoped memory operations, script-friendly output, and server-scalable architecture assumptions. |
| MMCP-003 | Track 1: Auto-capture + distillation | P0 | Ready | Migrated from GitHub issue #3. Implement hook-driven auto-capture of Claude Code session events into a Postgres-backed staging queue, background distillation into typed scoped memories, and automatic compressed context on `UserPromptSubmit`. |
| MMCP-004 | Define SafeMemoryContract for trusted durable memory | P0 | Backlog | Migrated from GitHub issue #4. Define durable memory trust classes, provenance requirements, executable-instruction rules, sensitivity defaults, confidence requirements, lifecycle behavior, and retrieval/rendering defaults. |
| MMCP-005 | Add durable compiled memory views with source provenance | P1 | Backlog | Migrated from GitHub issue #5. Define derived wiki-style memory projections such as project summaries, user preference summaries, active decision summaries, stale/conflict reports, and memory health reports without replacing structured memory as source of truth. |

## Decisions

### MMCP-D-001 — Repo file backlog is source of truth

**Decision:** use the repo-local file backlog as the planning source of truth for `memory-mcp`.

**Supersedes:** GitHub issue #2, which previously said GitHub Issues should track execution and handoffs for the standalone memory-MCP enhancement roadmap.

**Policy:** GitHub Issues may still be created for selected implementation-ready stories, concrete bugs, test failures, or follow-up work, but broad planning/backlog state belongs in `backlog/CANONICAL_BACKLOG.md` or another dedicated file under `backlog/`.

## Story detail

### MMCP-001 — Implement scheduled Memory Dream consolidation worker

**Behavior:** add a scheduled memory-consolidation process that periodically cleans and promotes memory instead of only appending raw observations.

**Intent:** give `memory-mcp` an explicit “dream pass” that turns noisy accumulated memory into compact, scoped, evidence-preserving long-term context.

**Recommended pipeline:**

```text
Raw observations
  ↓
Session summaries
  ↓
Project/person scoped memories
  ↓
Scheduled Memory Dream consolidation job
  ↓
Pruned, deduped, indexed long-term memory
```

**Functional requirements:**

- Add a callable consolidation service distinct from normal retrieval and existing pruning.
- Identify duplicate or overlapping active memories within bounded scope windows.
- Merge compatible memories into clearer summaries while preserving provenance links.
- Detect conflicting facts and mark them for review or supersession rather than silently overwriting them.
- Archive stale, low-value, or superseded records without physically deleting important evidence.
- Promote stable repeated facts into the correct memory scope: global, workspace, project, component, topic, or `scope_path`.
- Emit pruning/consolidation/audit records for every automated change.
- Provide a dry-run mode that reports planned changes without mutation.
- Support safe scheduling from a server deployment without assuming a single local desktop process.

**Acceptance criteria:**

- A testable consolidation service exists and can run in dry-run and apply modes.
- Duplicate memories can be merged with provenance preserved.
- Conflicting memories are not silently merged.
- Stale or superseded memories are archived according to explicit rules.
- Promoted memories retain links back to source memories/evidence.
- The process is bounded by scope, result limits, and time/window controls so it is safe for larger deployments.
- The job writes auditable consolidation results.
- Documentation explains the difference between normal pruning, context synthesis, and Memory Dream consolidation.

**Out of scope for first slice:**

- Fully autonomous unreviewed sensitive/private-memory rewriting.
- LLM-only conflict resolution without deterministic guardrails.
- Cross-user consolidation without explicit tenant/auth boundaries.
- Replacing the existing `run_pruning_pass` behavior wholesale.

### MMCP-002 — Build CLI for memory-MCP

**Behavior:** add a first-class CLI for interacting with memory-MCP outside MCP chat adapters.

**Intent:** allow humans, scripts, automations, and future ai-os components to create, retrieve, inspect, administer, and manage memory directly from the terminal while preserving the shared-service/server-scalable architecture.

**Functional requirements:**

- Add a CLI entry point for memory-MCP.
- Support memory create/search/list/detail/update/archive flows.
- Support scoped operations including global, workspace, project, component, topic, and `scope_path`.
- Support script-friendly output formats such as JSON.
- Support auth profiles, server URL configuration, and default scope/workspace/project settings.
- Avoid duplicating business logic already implemented in services or MCP boundaries.
- Support safe destructive operations through confirmations or explicit force flags.
- Document local Docker usage and future hosted/server usage.

**Acceptance criteria:**

- CLI works independently of Claude, Codex, Discord, or other chat adapters.
- CLI uses the same shared memory service and persistence path as MCP operations.
- Output is usable by both humans and scripts.
- Auth/configuration behavior is documented.
- Core commands are covered by automated tests.
- At least one end-to-end CLI happy path exists against a test or mocked service.

**Out of scope for first slice:**

- Full TUI/interactive dashboard workflows.
- Embedded local-only memory engines separate from the shared service.
- Rich web administration UI.

### MMCP-003 — Track 1: Auto-capture + distillation

**Source of truth references:**

- Roadmap: `docs/prompts/ROADMAP.md`
- Prompt: `docs/prompts/impl-auto-capture.md`
- Full plan: `docs/superpowers/plans/2026-05-07-auto-capture-distillation.md`

**Priority / status:**

- Priority: P0-equivalent roadmap foundation track
- Status: Ready
- Model: Sonnet
- Estimated effort: 1–2 days
- Branch: `feat/auto-capture-distillation`

**Goal:** add hook-driven auto-capture of Claude Code session events into a Postgres-backed staging queue, with a background distiller that compresses raw observations into typed scoped memories using model-routed Claude calls. Surface compressed context automatically on `UserPromptSubmit`.

**Implementation instructions:**

1. Branch off `main` as `feat/auto-capture-distillation`.
2. Read `docs/prompts/impl-auto-capture.md`.
3. Read `docs/superpowers/plans/2026-05-07-auto-capture-distillation.md` in full.
4. Use `superpowers:subagent-driven-development` or `superpowers:executing-plans`.
5. Implement task-by-task exactly as written.
6. Run `pytest` after each task and fix failures before continuing.
7. Run `alembic upgrade head` after the migration task.

**Key files:**

Create:

- `migrations/versions/0010_staging_observations.py`
- `src/memory_mcp/models/staging.py`
- `src/memory_mcp/repositories/staging.py`
- `src/memory_mcp/distiller/__init__.py`
- `src/memory_mcp/distiller/router.py`
- `src/memory_mcp/distiller/prompts.py`
- `src/memory_mcp/distiller/service.py`
- `src/memory_mcp/distiller/runner.py`
- `hooks/post_tool_use.py`
- `hooks/user_prompt_submit.py`
- `hooks/session_start.py`
- `hooks/session_end.py`
- `hooks/_client.py`
- `tests/test_staging_repository.py`
- `tests/distiller/test_router.py`
- `tests/distiller/test_service.py`
- `tests/hooks/test_post_tool_use.py`
- `tests/hooks/test_user_prompt_submit.py`
- `docs/auto_capture.md`

Modify:

- `src/memory_mcp/mcp_tools/server.py` — add `enqueue_observation`, `get_memory_by_id`
- `src/memory_mcp/models/__init__.py` — export `StagingObservation`
- `docker-compose.yml` — add `distiller` service
- `pyproject.toml` — add `anthropic` dependency
- `README.md` — link to `docs/auto_capture.md`

**Verification:**

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_staging_repository.py tests/distiller/ tests/hooks/ -v
alembic upgrade head
```

**Completion criteria:**

- Track 1 implemented and merged to `main`.
- `docs/prompts/ROADMAP.md` updated: Track 1 status changed from ⬜ to ✅.
- Handoff prompt for Track 2 is ready.

### MMCP-004 — Define SafeMemoryContract for trusted durable memory

**Goal:** define a `SafeMemoryContract` so durable memories are not treated as one flat trusted text bucket.

**Problem:** `memory-mcp` has sensitivity, scope, lifecycle, provenance/evidence, confidence, auth, audit, and bounded retrieval, but those concepts are distributed across schema, docs, tools, and retrieval behavior. As more agents write memory, the project needs one named contract that prevents unsafe promotion of retrieved memory into executable instruction.

**Proposed contract dimensions:**

Define memory classes such as:

- observation / evidence
- user-authored preference
- project decision
- agent-generated summary
- inferred memory
- executable instruction / workflow rule
- policy or safety rule

For each class, define:

- trust level
- required provenance
- whether it may directly influence future agent behavior
- whether it can be used as executable instruction
- sensitivity defaults
- confidence requirements
- lifecycle rules
- retrieval/rendering defaults

**Acceptance criteria:**

- Add a `SafeMemoryContract` design doc under `docs/`.
- Define supported memory classes and trust levels.
- Define how evidence/provenance, sensitivity, scope, lifecycle, confidence, and source actor interact.
- Define explicit rules for when memory may become executable instruction.
- Define default behavior for agent-generated summaries and inferred memories as lower-trust derived artifacts.
- Define validation requirements for future `add_memory` / `supersede_memory` write paths.
- Cross-link from `docs/ARCHITECTURE.md`, `docs/GOALS.md`, and `docs/README.md`.

**Non-goals:**

- Do not rebuild the storage schema unless the contract exposes a required missing field.
- Do not make generated summaries canonical truth.
- Do not allow arbitrary retrieved text to silently override policy or workflow instructions.
- Do not require hosted/multi-user behavior beyond the existing remote-auth direction.

### MMCP-005 — Add durable compiled memory views with source provenance

**Goal:** add durable compiled memory views to `memory-mcp`: generated human/agent-readable summaries backed by structured memory source records and provenance links.

**Problem:** `memory-mcp` synthesizes task-scoped context packets and stores structured memory with provenance. That solves immediate retrieval, but it does not yet clearly define durable wiki-style projections such as project summaries, active decision summaries, user preference summaries, or stale/conflict reports.

**Proposed compiled view types:**

- project summary
- component summary
- user preference summary
- active decisions summary
- current workflow/rules summary
- stale/conflict report
- memory health report

**Acceptance criteria:**

- Add or update design documentation for durable compiled memory views.
- Define compiled views as derived artifacts, not canonical truth.
- Define source-memory provenance links for each compiled view.
- Define stale/invalidated state when source memories are archived, superseded, deleted, or changed.
- Define how compiled views relate to existing `context_packets`.
- Define retrieval behavior: when agents may use a compiled view directly and when they must verify against source memory.
- Identify whether existing schema can support this or whether a small schema migration is needed.
- Add follow-up implementation slices only after the design is accepted.

**Non-goals:**

- Do not replace structured memory records with markdown/wiki prose.
- Do not duplicate external source-of-truth systems such as GitHub issues.
- Do not make compiled summaries executable instructions unless they satisfy the future `SafeMemoryContract`.
- Do not build a broad UI in this story.

## Migrated GitHub issue record

| Issue | New backlog location | Status |
|---|---|---|
| #2 — Decision: Track memory-mcp prompt-generated enhancements in GitHub issues | MMCP-D-001 | Superseded by file-backlog policy |
| #3 — Track 1: Auto-capture + distillation | MMCP-003 | Migrated |
| #4 — Define SafeMemoryContract for trusted durable memory | MMCP-004 | Migrated |
| #5 — Add durable compiled memory views with source provenance | MMCP-005 | Migrated |
| #6 — Build CLI for memory-MCP | MMCP-002 | Migrated earlier |

## Backlog maintenance rules

When adding or updating stories:

1. Keep IDs stable.
2. Prefer updating an existing story over adding a conflicting duplicate.
3. Add implementation detail only when the story is near execution.
4. Keep broad epics separate from implementation-ready stories.
5. Move selected stories into `.ai/specs/` before coding.
6. Create GitHub Issues only for selected implementation-ready stories or discovered bugs/follow-ups.
