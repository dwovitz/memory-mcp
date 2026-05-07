# memory-mcp Agent Workflow

Use the `memory-mcp` MCP server as the durable project context layer.

Before substantial implementation, review, debugging, or planning:

- Call `get_context_packet` with the narrowest useful scope.
- Use `workspace="ai"` or the local workspace root name.
- Use `project="<repo-name>"` for the current repository.
- Use `repo="<repo-name>"` when the memory server exposes the repo scope layer,
  especially in workspaces where one project spans multiple repositories.
- Add `component="<subsystem>"` only when the subsystem is clear.
- Set `include_global=true` and `include_sensitive=false`.
- Inspect `context_quality`, `suggested_next_action`, `source_read_policy`,
  `source_read_budget_tokens`, `source_read_limits`, and
  `source_read_contract` before reading source.

Source-read discipline:

- Treat `source_read_contract` as the hook-friendly source of truth.
- Track pre-edit source file count, source snippet count, and max lines per
  snippet.
- Path-only discovery does not count as source context.
- `Select-String -List` is path-only discovery; `Select-String` output with
  matching source lines is a source snippet read.
- bounded snippets count toward `max_snippets`.
- Stop at `source_read_contract.pre_edit_limits.max_snippets` before the first
  edit.
- Staying under `max_lines_per_snippet` is not enough if `max_snippets` is
  exceeded.
- If more snippets are needed before the first edit, record an exception before
  exceeding the budget. Name the missing fact, likely file or symbol, and why
  current bounded snippets are insufficient.
- Mark `source_read_budget_obeyed: no` when any
  `source_read_contract.failure_conditions` entry applies.

After meaningful project work:

- Refresh durable project memory using mutation tools only when enabled for a
  trusted local client.
- Store compact, non-sensitive project facts.
- Do not store secrets, raw logs, transcripts, temporary debugging notes, or
  sensitive data.
- Report `project_memory_refreshed: yes/no` in task closeout when relevant.
