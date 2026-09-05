Save a durable memory for the memory-mcp project using `add_memory`.

Use this scope for project-level facts:

```
add_memory(
  summary="<one-line summary>",
  content="<full detail>",
  memory_type="<type>",
  workspace="ai",
  project="memory-mcp",
  repo="memory-mcp"
)
```

Common `memory_type` values:
- `architecture_decision` — accepted design choices, ADR outcomes
- `project_fact` — environment constraints, known bugs with root cause
- `project_rule` — workflow rules, process constraints
- `workflow_location` — where key files or tools live
- `coding_preference` — confirmed code style or tooling decisions

Do NOT save: speculation, code-derivable facts, secrets, credentials, raw logs, or transcripts.

After saving, report `project_memory_refreshed: yes` in your response.
