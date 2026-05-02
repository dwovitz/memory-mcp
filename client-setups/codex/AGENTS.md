# memory-mcp Workflow

Use the `memory-mcp` MCP server for durable project memory.

## Retrieval

Before substantial implementation, review, debugging, or planning, call
`get_context_packet` with the narrowest useful scope:

```text
workspace="ai"
project="<repo-name>"
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

