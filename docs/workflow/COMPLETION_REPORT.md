# Completion Report Format

Durable completion-report contract for memory-mcp story work.

Use for implementation passes, documentation-only workflow changes, fixer passes, review closeouts, and blocked handoffs. The report lives inside a handoff file but must preserve this evidence shape.

## Location

Each story pass produces a durable handoff artifact:

```text
.ai/handoffs/<YYYY-MM-DD>-<story-id>-handoff.md
```

Use `.ai/prompts/HANDOFF_TEMPLATE.md` as the concrete Markdown template.

## Status Values

| Status | Meaning |
|---|---|
| `complete` | Acceptance criteria implemented, validated, reconciled, and ready for next phase. |
| `needs_review` | Implementation evidence ready for independent review before acceptance. |
| `partial` | Some scoped work complete; known story scope remains. |
| `validation_failed` | Required validation was run and failed; command and failure summary are recorded. |
| `blocked` | Work cannot safely continue; exact blocker is recorded. |

Do not use `complete` for work that was not freshly validated.

## Required Sections

Every completion report must include:

```markdown
## Story
## Status
## What Was Implemented
## Validation Performed
## Evidence
## Changed Files
## Backlog Reconciliation
## Git / Push Status
## Risks / Limitations
## Follow-up Recommendations
## Next Step Packet
```

The handoff template may include additional sections (Routing, Review, TDD evidence, Friction notes, Self-improvement scan). Extra sections are allowed; omitting required sections is not.

## Story Section

Record:
- story ID and title
- branch and worktree path
- model and effort used for the current pass
- role performed

## Evidence Section

Each evidence record must include:
- Type: `command | review | backlog-check | git | manual-inspection`
- Exact command or `n/a`
- Exit code or result
- Relevant output snippet
- What it supports

## Backlog Reconciliation Section

Before closing out a story, reconcile status across:
- `backlog/CANONICAL_BACKLOG.md`
- `backlog/STORY_INDEX.csv`
- `docs/backlog/IMPLEMENTATION_ORDER.md`

Record the commit SHA for the backlog update commit, or an explicit reason it is not applicable.

## Next Step Packet (required)

Every report ends with a Next Step Packet that names:
- completed step summary
- current story and status
- validation run result
- git status and commit SHA
- next story
- next model/effort/role
- why this routing is correct
- stop/continue decision
- blocker, if any
- copy-paste prompt for the next session
