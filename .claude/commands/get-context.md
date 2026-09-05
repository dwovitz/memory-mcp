Call `get_context_packet` for the memory-mcp project before starting any substantial work.

Use this scope:

```
get_context_packet(
  request="<describe what you are about to do>",
  workspace="ai",
  project="memory-mcp",
  repo="memory-mcp",
  include_global=true,
  include_sensitive=false
)
```

Inspect the returned fields before reading any source files:

- `context_quality` — strong | moderate | weak
- `suggested_next_action` — what to do next
- `source_read_policy` — answer_from_packet | verify_narrowly | mark_weak_context
- `source_read_budget_tokens` — how many tokens of source reading are budgeted

Follow `source_read_policy` strictly. If `answer_from_packet`, skip source reads.
If `verify_narrowly`, read only 1–2 specific snippets to confirm a fact.
If `mark_weak_context`, inspect source before answering but keep reads bounded.
