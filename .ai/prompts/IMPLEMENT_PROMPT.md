# Implement Prompt

Use this prompt for implementation passes.

```text
You are implementing one memory-mcp story.

Read:
1. CLAUDE.md
2. backlog/CANONICAL_BACKLOG.md
3. backlog/STORY_INDEX.csv
4. docs/backlog/IMPLEMENTATION_ORDER.md
5. .ai/orchestration/STORY_WORKFLOW.md
6. .ai/orchestration/DEFINITION_OF_DONE.md
7. docs/workflow/COMPLETION_REPORT.md
8. The selected repo-local story spec
9. Only the source files needed for this slice

Before reading source files:
- Call get_context_packet(workspace="ai", project="memory-mcp", repo="memory-mcp", component="<subsystem>")
- Use code-review-graph MCP tools (semantic_search_nodes, get_impact_radius, query_graph) before Grep/Read.

Rules:
- Stay inside the selected story scope.
- Use TDD where practical: write the failing test first, then implement the smallest passing change.
- Refactor only after green tests.
- Do not implement infrastructure outside the story.
- Do not change schema without an Alembic migration.
- Preserve clean architecture: MCP tool layer stays thin (validate → authorize → delegate to service).
- If the spec must change, update it before continuing.

Syntax check after server.py changes:
  python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"

Validation:
  pytest

Before producing the handoff, reconcile story status across all three controlling backlog files:
- backlog/CANONICAL_BACKLOG.md
- backlog/STORY_INDEX.csv
- docs/backlog/IMPLEMENTATION_ORDER.md
Commit backlog updates as a focused docs/backlog commit before the handoff. Record the commit SHA in the handoff's Backlog Reconciliation section.

Output:
- files changed
- tests added/changed
- validation output
- TDD evidence
- deviations from spec
- backlog reconciliation (commit SHA or reason not applicable)
- risks/follow-ups
- handoff conforming to docs/workflow/COMPLETION_REPORT.md
```
