# memory-mcp Workflow

Use the `memory-mcp` MCP server for durable project memory.

Before substantial implementation, review, debugging, or planning:

- Call `get_context_packet` using the narrowest scope.
- Prefer `workspace="ai"`, `project="<repo-name>"`, and a clear `component`
  when available.
- Use `include_global=true`.
- Keep `include_sensitive=false` unless the user explicitly asks for sensitive
  memory.
- Read `source_read_contract` before source inspection.

Source-read contract rules:

- Keep pre-edit counters for files, snippets, and snippet line counts.
- Bounded snippets count toward `max_snippets`.
- Stop at `source_read_contract.pre_edit_limits.max_snippets` before the first
  edit.
- Record an exception before exceeding the contract. Name the missing fact,
  likely file or symbol, and why current bounded snippets are insufficient.
- Set `source_read_budget_obeyed: no` if a contract failure condition applies.

After meaningful project work, refresh memory with durable, non-sensitive facts
when mutation tools are enabled. Report `project_memory_refreshed: yes/no` in
closeout when relevant.

