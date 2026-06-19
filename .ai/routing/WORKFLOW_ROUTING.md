# Workflow Routing

This file defines how work should be phased and routed between Claude Code sessions.

The goal is high-quality output with minimal wasted context. Default to the smallest effective workflow.

## Canonical model registry

`.ai/model-routing-registry.yaml` is the canonical source of truth for harness ids, model ids, effort ids, defaults, fallback behavior, and disallowed values.

Routing agents must not invent harness names, model names, or effort labels. Every handoff that recommends a next tool must use only values allowed by `.ai/model-routing-registry.yaml`.

Required routing output shape:

```yaml
harness: claude
model: sonnet
effort: medium
role: coder
source: .ai/routing/WORKFLOW_ROUTING.md + .ai/model-routing-registry.yaml
```

## Default workflow

1. **Plan** — Claude Code classifies the story, checks Definition of Ready, identifies affected files and boundaries, writes or updates the spec, and defines the test approach.
2. **Implement** — Claude Code implements the selected slice with TDD, validates, and fixes.
3. **Review** — Claude Code (ideally a fresh session) reviews the diff for acceptance criteria, architecture, clean code, security, and handoff quality.
4. **Handoff** — compact handoff plus `Next Step Packet` instead of long chat transcript.

Do not bounce between planning and implementation for every micro-step.

## Story-size routing

### XS / Low-risk

Examples: docs-only, small config edits, adding a constant.

- Planning: optional if the story is clear.
- Implementation and review: single `normal_coding` session.
- Security review: lightweight checklist only.

### S / Standard

Examples: new MCP tool wrapper, small helper function, one-table migration.

- Claude Code plans once (sonnet / medium).
- Claude Code implements and validates.
- Claude Code reviews after the slice is complete.

### M / Standard or High risk

Examples: new `src/memory_mcp/` service module, embedding pipeline, ingestion package.

- Claude Code plans with architecture notes (sonnet / high for schema or retrieval work).
- Claude Code implements in bounded slices.
- Independent Claude Code session reviews each completed slice.
- Security review runs separately when the story touches auth, secrets handling, or persistence.

### L or Critical

Split before coding. Submit the split as a docs-only spec update first.

## Subagent triggers

Spawn a subagent when:
- Two or more independent bounded tasks can run in parallel.
- The story touches both service and MCP-tool layers.
- An independent reviewer is needed (implementer has confirmation bias).
- Output would bloat the main context window (e.g., large file scans).

Do not spawn when:
- The task is a one-file docs edit.
- The subagent would read the same context and produce no independent artifact.

## Phase routing table

| Phase | Route key | Harness | Model | Effort |
|---|---|---|---|---|
| Docs / config only | `cheap_edit` | claude | haiku | low |
| Story planning | `daily_coding` | claude | sonnet | medium |
| Architecture planning | `daily_coding` | claude | sonnet | medium |
| Deep architecture tradeoffs | `architecture_review` | claude | opus | high |
| Normal implementation | `normal_coding` | claude | sonnet | medium |
| Schema/retrieval/embedding work | `difficult_coding` | claude | sonnet | high |
| Clean-code review | `daily_coding` | claude | sonnet | medium |
| Security-sensitive review | `security_review` | claude | sonnet | high |
| Independent judge review | `daily_coding` | claude | sonnet | medium |
| Plan-then-execute (large story) | `plan_then_execute` | claude | opusplan | medium |

## Effort escalation rules

Start with medium for normal planning and implementation.

Escalate to high when the story includes:
- schema migrations or index additions
- retrieval re-ranking logic
- embedding pipeline
- auth or secrets-handling changes
- repeated failed implementation loops
- conflicting decisions or backlog entries

Use `opus` only when the planner or reviewer records an explicit escalation rationale and expected value.

## Handoff requirements

Every handoff must record:
- model and effort used
- role performed
- routing decision and source
- whether subagents were spawned and why
- whether any escalation occurred
- the recommended next model/effort/role
- confirmation that next values were validated against `.ai/model-routing-registry.yaml`
