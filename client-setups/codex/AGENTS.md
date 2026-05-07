# memory-mcp Workflow

Use the `memory-mcp` MCP server for durable project memory.

## Retrieval

Before substantial implementation, review, debugging, or planning, call
`get_context_packet` with the narrowest useful scope:

```text
workspace="ai"
project="<repo-name>"
repo="<repo-name>"       # optional: narrows within a multi-repo project
component="<subsystem when clear>"
include_global=true
include_sensitive=false
max_memories=8
max_tokens=1200
```

Inspect `context_quality`, `warnings`, `suggested_next_action`,
`source_read_policy`, `source_read_budget_tokens`, `source_read_limits`, and
`source_read_contract` before reading source.

## Source Budget Contract

For repository work, treat `source_read_contract` as the source-read source of
truth.

- Track source files, source snippets, and lines per snippet before the first
  edit.
- Bounded snippets count toward `max_snippets`.
- Stop at `source_read_contract.pre_edit_limits.max_snippets` before the first
  edit.
- Staying under `max_lines_per_snippet` is not enough if `max_snippets` is
  exceeded.
- If more source is needed before the first edit, record the exception before
  exceeding the limit. Name the missing fact, likely file or symbol, and why
  current bounded snippets are insufficient.
- Report `source_read_budget_obeyed: no` if any contract failure condition
  applies.

## Memory Refresh

After meaningful project changes, refresh memory with compact, non-sensitive
facts when mutation tools are enabled. Report `project_memory_refreshed: yes/no`
in the final response when relevant.

## Code Exploration — Graph First

Use code-review-graph MCP tools before grep or file reads:

- `semantic_search_nodes` or `query_graph` for symbols, imports, callers, callees, and tests.
- `get_impact_radius` before edits that may affect callers or dependents.
- `detect_changes` plus `get_review_context` for code review.
- `get_architecture_overview` for architecture questions.

Fall back to file reads only when the graph does not cover what you need or the graph tool is unavailable. If unavailable, state that and keep reads bounded.

## Model Routing

When spawning Codex subagents, use the smallest model that preserves quality:

| Task type | Model |
|-----------|-------|
| File search, codebase exploration, log scanning | `gpt-5.4-mini` with low/medium reasoning |
| Implementation, editing code, writing tests | `gpt-5.4` or inherit current model |
| Architecture decisions, complex debugging | `gpt-5.5` with high/xhigh reasoning |

- `gpt-5.4-mini` subagents are read-only only.
- Always cap `gpt-5.4-mini` briefs: "report in under 150 words" or "return a structured list only".
- If a listed model is unavailable, use the closest available smaller model for read-only work and the inherited model for implementation.

## Agent Dispatch Patterns

Spawn a subagent when:
- A task is purely read-only search, summarization, or log scanning.
- Two or more independent tasks can run in parallel.
- A task would produce large output the main session does not need verbatim.

Always brief subagents with the task goal, relevant paths or search terms, output format, word cap, and whether they are read-only or may edit.
