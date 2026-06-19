# Agent Work Protocol

Standard development pass for agents working on `memory-mcp`. Coordinates the source-of-truth backlog, worktree strategy, story workflow, routing registry, and handoff template.

## Status Values

| Status | Meaning |
|---|---|
| `complete` | Acceptance criteria implemented, validated, reconciled, and ready for the next workflow phase. |
| `needs_review` | Implementation pass is ready for independent review before acceptance. |
| `partial` | Some bounded work is complete, but known story scope remains. |
| `validation_failed` | Required validation was run and failed; the exact command and failure summary are recorded. |
| `blocked` | Work cannot safely continue without a decision, credential, environment access, or clearer requirements. |

## Protocol

1. Select exactly one active story from the repo-local backlog.
2. Verify the story spec under `.ai/specs/`; create or update before implementation if missing or stale.
3. Call `get_context_packet(workspace="ai", project="memory-mcp", repo="memory-mcp")` before broad source reads.
4. Use code-review-graph MCP tools (`semantic_search_nodes`, `get_impact_radius`, `query_graph`) before Grep/Read.
5. Create or re-enter the dedicated story worktree using `docs/workflow/WORKTREE_STRATEGY.md`.
6. Classify size, risk, routing, and review depth using `.ai/routing/WORKFLOW_ROUTING.md`.
7. Produce or update a short implementation plan for the selected story.
8. Make bounded changes only for the selected story. Do not opportunistically work adjacent items.
9. Run validation from inside the story worktree. Include exact commands and output in the durable report.
10. Reconcile story status across the controlling backlog surfaces before handoff:
    - `backlog/CANONICAL_BACKLOG.md`
    - `backlog/STORY_INDEX.csv`
    - `docs/backlog/IMPLEMENTATION_ORDER.md`
11. Produce durable handoff artifact: `.ai/handoffs/<date>-<story-id>-handoff.md`
    - Contents must conform to `docs/workflow/COMPLETION_REPORT.md`.
12. Record changed files, validation evidence, risks, branch/worktree path, and commit/push status.
13. End with the mandatory **Next Step Packet** using registry-valid `model` and `effort` values from `.ai/model-routing-registry.yaml`.

## Main-Branch Guardrail

Do not implement stories directly on `main`. Story work happens in a dedicated worktree and branch. The main checkout is used only for source-of-truth inspection and merge/reconciliation after the story branch is complete.

## Story Scope Guardrail

One pass means one story. If a needed change belongs to another story, capture it as a follow-up in the spec, handoff, backlog, or friction log.

## Completion Evidence

The detailed completion report and evidence schema lives in `docs/workflow/COMPLETION_REPORT.md`.

Completion reports must include evidence, not claims:
- active story ID and title
- branch and worktree path
- final status value
- acceptance criteria summary
- changed files summary
- validation command, exit result, and relevant output
- backlog reconciliation summary
- commit SHA and push status, or the exact reason they are not available

## Next-Capability Checkpoint

Every pass ends with a **Next Step Packet**. It names the recommended next story, route, reason, stop/continue decision, blocker if any, and a copy-ready prompt for the next session.
