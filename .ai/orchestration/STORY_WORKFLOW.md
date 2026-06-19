# Story Workflow

For the concise development-pass protocol, use `docs/workflow/AGENT_WORK_PROTOCOL.md`. This file is the detailed lifecycle, loopback, review, friction, and continuation policy.

Allowed workflow status values:

- `complete`
- `needs_review`
- `partial`
- `validation_failed`
- `blocked`

## Required flow

1. Select one story.
2. Check Definition of Ready (`DEFINITION_OF_READY.md`).
3. Classify size and risk.
4. Classify workflow routing using `.ai/routing/WORKFLOW_ROUTING.md`.
5. Retrieve only necessary context (`get_context_packet` before broad source reads).
6. Create or update story spec in `.ai/specs/MMCP-###-short-kebab-name.md`.
7. Produce or update the implementation plan.
8. Create or re-enter the story worktree using `docs/workflow/WORKTREE_STRATEGY.md`.
9. Implement with TDD when the story changes product code or behavior.
10. Run validation from inside the story worktree.
11. Run independent AI review/judge phase.
12. Run clean-code review.
13. Run scaled security review for high-risk work.
14. Reconcile story status across the controlling backlog files.
15. Append any workflow friction observed during this pass to `.ai/improvement/FRICTION_LOG.md`.
16. Evaluate self-improvement scan triggers (see "Self-improvement scan" below).
17. Produce handoff to `.ai/handoffs/<date>-<story-id>-handoff.md`.
18. Emit the mandatory `Next Step Packet`.
19. Select and route the next eligible story unless a stop condition blocks continuation.

## Story specs

Every implementation story must have a repo-local story spec before coding starts.

Location: `.ai/specs/MMCP-###-short-kebab-name.md`

Story specs are lightweight execution contracts, not design documents. Stay under 200 lines. Capture only what is needed to implement, test, review, and hand off.

Story specs must:
- define observable acceptance criteria
- define explicit non-goals
- define validation expectations
- define documentation impact
- preserve architectural boundaries

Update the spec during implementation when scope, acceptance criteria, test plan, or validation changes.

## Independent AI review/judge phase

Purpose:
- verify story acceptance criteria
- verify architecture-boundary compliance
- detect scope creep
- verify test adequacy
- identify security/privacy concerns
- verify workflow compliance

Guidelines:
- Prefer a reviewer independent from the implementing session.
- Prefer a stronger reviewer for high-risk stories (schema migrations, auth, retrieval changes).
- Low-risk docs-only stories may use lightweight review.

Allowed outcomes: approve, approve with notes, request changes, escalate.

## Routing classification

Before implementation record:
- story size (XS / S / M / L)
- risk level (Low / Standard / High / Critical)
- required phases
- whether separate agents/subagents are justified
- selected model/effort per phase
- escalation rationale, if any

## Allowed loopbacks

- Review can return to implementation.
- Security review can return to design or implementation.
- Failed validation can return to implementation.
- Unclear scope returns to story refinement.

## Continuation after every step

Every implementation, test-fix, review, judge review, security review, documentation-only change, backlog closeout, or blocked state must end with the `Next Step Packet` from `.ai/prompts/HANDOFF_TEMPLATE.md`.

Continue automatically unless one of these blockers exists:
- no eligible next story
- multiple equally valid next stories with no ordering rule
- ambiguous or incomplete requirements
- failing validation that cannot be safely resolved
- missing environment access
- required user confirmation for an external side effect
- explicit one-story-only user instruction

## Backlog reconciliation gate

Before producing the handoff for an implementation, review pass, or closeout, reconcile the story across all controlling backlog surfaces:

- `backlog/CANONICAL_BACKLOG.md`
- `backlog/STORY_INDEX.csv`
- `docs/backlog/IMPLEMENTATION_ORDER.md`

Commit backlog updates as a focused docs/backlog commit before final closeout. Record the commit SHA (or reason not applicable) in the handoff.

## Self-improvement scan

Friction logging (every pass):
- Append entries to `.ai/improvement/FRICTION_LOG.md` for any redo, routing correction, mis-scoped context, missing tool, unclear template field, recurring manual step, or validated non-obvious approach.
- If no friction was observed, record `friction_logged: none-observed` in the handoff.

Scan triggers (run scan when either holds):
- five or more `scan status: open` entries exist in `.ai/improvement/FRICTION_LOG.md`, or
- any open entry has `category: redo` or `category: routing`.

Scan execution:
- Run as a Claude planning/review role.
- Apply only `auto`-tier changes (docs/test-only). Emit `shadow`- and `approval`-tier proposals to `.ai/improvement/proposals/`.
- Update consumed friction entries to `scan status: consumed-YYYY-MM-DD`.

## Stop conditions

Stop and hand off instead of continuing when:
- story is not ready
- required story spec is missing or materially outdated
- scope expands beyond story
- implementation requires an unaccepted decision
- more than two implementation loops fail
- more than two review loops fail
- security review requires escalation
- context becomes bloated

Stopping still requires a `Next Step Packet` with the exact blocker and a copy-paste prompt for the next session.

## Context budget defaults

- maximum 12 context files per pass
- spec target: ≤ 200 lines
- handoff target: ≤ 120 lines
- prefer fresh session plus compact handoff over dragging long context forward
