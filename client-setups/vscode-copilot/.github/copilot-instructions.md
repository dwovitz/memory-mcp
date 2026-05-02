# memory-mcp Workflow

Use the `memory-mcp` MCP server as the durable project context layer.

Before substantial implementation, review, debugging, or planning:

- Call `get_context_packet` with the narrowest useful scope.
- Use `workspace="ai"` and `project="<repo-name>"`.
- Include `component="<subsystem>"` when the subsystem is clear.
- Use `include_global=true`.
- Keep `include_sensitive=false` by default.
- Inspect `source_read_contract` before reading source.

Source-read rules:

- Track pre-edit source files, snippets, and snippet line counts.
- Bounded snippets count toward `max_snippets`.
- Stop at `source_read_contract.pre_edit_limits.max_snippets` before the first
  edit.
- Staying under `max_lines_per_snippet` is insufficient if `max_snippets` is
  exceeded.
- If more pre-edit source is necessary, record an exception before exceeding the
  contract. Name the missing fact, likely file or symbol, and why current
  bounded snippets are insufficient.
- Report `source_read_budget_obeyed: no` when a contract failure condition
  applies.

After meaningful project changes, refresh durable non-sensitive memory when
mutation tools are enabled. Report `project_memory_refreshed: yes/no` when
relevant.

