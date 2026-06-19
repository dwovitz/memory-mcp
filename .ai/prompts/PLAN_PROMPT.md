# Plan Prompt

Use this prompt for story planning.

```text
You are planning work for memory-mcp.

Read:
1. CLAUDE.md
2. backlog/CANONICAL_BACKLOG.md
3. backlog/STORY_INDEX.csv
4. docs/backlog/IMPLEMENTATION_ORDER.md
5. .ai/orchestration/STORY_WORKFLOW.md
6. .ai/orchestration/DEFINITION_OF_READY.md
7. .ai/routing/WORKFLOW_ROUTING.md
8. The selected backlog story/spec
9. Any linked decisions or design notes

Task:
- Call get_context_packet(workspace="ai", project="memory-mcp", repo="memory-mcp") before reading source files.
- Confirm the story is present in the repo backlog or a repo-local spec.
- Confirm the story satisfies the Definition of Ready.
- Classify size and risk.
- Classify workflow routing using .ai/routing/WORKFLOW_ROUTING.md.
- Identify affected boundaries (MCP tool layer, service, repository, migration).
- Produce a concise spec under .ai/specs/ when one is missing or stale.
- Define tests first.
- List explicit out-of-scope items.
- Stop if the story is too large, depends on an unaccepted decision, or requirements are unclear.

Routing output required:
- required phases
- optional phases
- whether subagents are justified
- model/effort per phase
- escalation rationale, if any

Output:
- story ID
- readiness result
- size/risk
- routing plan
- spec path
- test plan
- validation command (always: pytest + python syntax check)
- next implementation prompt
```
