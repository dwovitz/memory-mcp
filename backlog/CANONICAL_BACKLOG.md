# Canonical Backlog

This file is the human-readable canonical backlog for `memory-mcp` implementation planning.

The repo-local backlog is the implementation source of truth for memory-MCP work. GitHub Issues should be created only when a story is selected for implementation or when a concrete bug/follow-up is discovered.

## Current source-of-truth policy

- New implementation stories are added here or to a dedicated markdown/CSV file under `backlog/`.
- Accepted architectural decisions should be captured in `docs/decisions/` when that decision-log structure exists.
- Selected stories should receive compact specs under `.ai/specs/` before coding when they need design detail.
- Design-heavy stories should receive design notes under `.ai/design/` before implementation.
- GitHub Issues are for implementation-ready selected stories, bugs, test failures, or concrete follow-ups.

## Immediate backlog sequence

### 1. Memory lifecycle and consolidation

| ID | Title | Priority | Status | Notes |
|---|---|---:|---|---|
| MMCP-001 | Implement scheduled Memory Dream consolidation worker | P0 | Backlog | Add an explicit consolidation pass inspired by Claude Code Auto Dream: review recent memory, merge duplicate or overlapping facts, resolve conflicts, prune stale/low-value entries, promote durable scoped memories, archive superseded detail, and write provenance/audit records. Must fit server-scalable PostgreSQL/pgvector architecture rather than local-only file cleanup. |

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

## Backlog maintenance rules

When adding or updating stories:

1. Keep IDs stable.
2. Prefer updating an existing story over adding a conflicting duplicate.
3. Add implementation detail only when the story is near execution.
4. Keep broad epics separate from implementation-ready stories.
5. Move selected stories into `.ai/specs/` before coding.
6. Create GitHub Issues only for selected implementation-ready stories or discovered bugs/follow-ups.
