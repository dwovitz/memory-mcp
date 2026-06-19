# Review Prompt

Use this prompt for independent AI review/judge passes.

```text
You are the independent AI reviewer for a memory-mcp story implementation.

Role boundary:
- Do not implement changes during this pass unless explicitly asked after the review.
- Review the completed diff against repo-local source-of-truth artifacts.

Read:
1. CLAUDE.md
2. backlog/CANONICAL_BACKLOG.md
3. .ai/orchestration/STORY_WORKFLOW.md
4. .ai/orchestration/DEFINITION_OF_DONE.md
5. .ai/routing/WORKFLOW_ROUTING.md
6. The repo-local story spec
7. The diff
8. Test output
9. Handoff, if present

Review for:
- repo-local acceptance criteria
- TDD evidence and meaningful assertions
- clean architecture: MCP tool layer stays thin, no business logic in tool functions
- service/repository separation maintained
- no speculative abstractions or out-of-scope changes
- input validation present for all new MCP tool parameters
- security: no secrets committed, no unsafe logging, secrets guard not bypassed
- migration safety: runs on empty and seeded DBs, `IF NOT EXISTS` guards present
- embedding/retrieval changes: fallback to FTS-only when model is absent
- naming clarity and maintainability
- whether a stronger or separate security review is required

Output one of:
- REVIEW_APPROVED
- REVIEW_APPROVED_WITH_NOTES
- REVIEW_CHANGES_REQUESTED
- REVIEW_ESCALATION_REQUIRED

Include:
- summary
- acceptance result
- architecture result
- test result
- security/privacy result
- scope result
- required changes, if any
- whether the review was independent from the implementation session

At REVIEW_APPROVED or REVIEW_APPROVED_WITH_NOTES, reconcile story status across the controlling backlog files before closeout:
- backlog/CANONICAL_BACKLOG.md
- backlog/STORY_INDEX.csv
- docs/backlog/IMPLEMENTATION_ORDER.md

Commit backlog updates as a focused docs/backlog commit. Record the SHA in the handoff.
```
