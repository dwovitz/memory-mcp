# Handoff Template

Use this template for every implementation pass, review pass, fixer pass, or blocked handoff.

```markdown
# Handoff — <STORY_ID> <title>

## Story

- ID:
- Title:
- Branch:
- Worktree:
- Status:
- Model used:
- Effort used:
- Role performed:

## Routing

- Routing policy used: `.ai/routing/WORKFLOW_ROUTING.md`
- Model registry used: `.ai/model-routing-registry.yaml`
- Workflow selected:
- Subagents spawned:
- Reason subagents were or were not spawned:
- Escalation used:
- Escalation rationale:

| Step | Model | Effort | Role | Reason |
|---|---|---|---|---|
| Planning |  |  |  |  |
| Implementation |  |  |  |  |
| Validation |  |  |  |  |
| Review |  |  |  |  |

## Spec/design

- Spec:
- Decisions referenced:

## Scope

- Completed:
- Not completed:
- Explicitly out of scope:

## What Was Implemented

- Implemented:
- Validation-backed status claim:
- Deviations from spec:

## Changed Files

- `<path>` — <reason>

## Backlog Reconciliation

- Checked `backlog/CANONICAL_BACKLOG.md`:
- Current story status there:
- Updated in this workflow:
- Checked `backlog/STORY_INDEX.csv`:
- Current story status there:
- Updated in this workflow:
- Checked `docs/backlog/IMPLEMENTATION_ORDER.md`:
- Current story status there:
- Updated in this workflow:
- Backlog commit SHA or reason not applicable:

## TDD evidence

- tdd_used:
- failing_test_observed:
- reason_if_no_failing_test:
- tests_added_or_changed:
- refactor_after_green:

## Validation Performed

- Command:
- Result:
- Relevant output:

## Evidence

### Evidence record: <short name>

- Type: command | review | backlog-check | git | manual-inspection
- Command: `<exact command>` or `n/a`
- Exit code/result:
- Relevant output:
- Supports:

## Git / Push Status

- Branch:
- Commit SHA:
- Pushed to origin:
- Final `git status`:

## Review

- Independent review performed:
- Reviewer independent from implementer:
- Model used for review:
- Effort used for review:
- Clean-code review status:
- Security review status:
- Security review depth:

## Friction notes

- Friction observed this pass:
- friction_logged: <count | none-observed>

## Self-improvement scan

- Trigger evaluated:
- Trigger fired: <cadence | correction | none>
- self_improvement_scan: <completed | skipped (no trigger) | deferred (blocker)>
- Proposal file: <path or n/a>

## Risks / Limitations

- Risk:

## Follow-up Recommendations

- Follow-up:
- Requires user decision:

## Next Step Packet

- Completed step:
- Current story:
- Current status:
- Validation run:
- Git status:
- Commit SHA(s):
- Next story:
- Next model:
- Next effort:
- Next role:
- Why this routing is correct:
- Stop/continue decision:
- Blocker, if any:
- Copy-paste prompt for next session:

<complete copy-ready prompt for the next session, or `none: no eligible next step` with the blocker>
```

The final chat response must include the `## Next Step Packet` section. If the workflow is blocked, keep the packet and put the exact blocker in both `Blocker, if any` and the copy-paste prompt field.
