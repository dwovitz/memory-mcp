# memory-mcp

PostgreSQL + pgvector memory service with MCP interface. Provides durable project memory across Claude and Codex sessions via Docker.

## Code Exploration — Graph First

Always use code-review-graph MCP tools before grep or file reads:

- `semantic_search_nodes` to find functions or classes by name/keyword
- `get_impact_radius` before any edit to understand blast radius
- `query_graph` with callers_of/callees_of to trace call chains
- `detect_changes` + `get_review_context` for code review
- Fall back to file reads only when the graph doesn't cover what you need.

## Model Routing

| Task type | Model |
|-----------|-------|
| File search, codebase exploration, log scanning | `gpt-5.4-mini` with low/medium reasoning |
| Implementation, editing code, writing tests | `gpt-5.4` or inherit current model |
| Architecture decisions, complex debugging | `gpt-5.5` with high/xhigh reasoning |

- `gpt-5.4-mini` subagents are read-only only — no file edits.
- Always cap `gpt-5.4-mini` briefs: "report in under 150 words" or "return a structured list only".
- If a listed model is unavailable in the active Codex runtime, use the closest available smaller model for read-only work and the inherited model for implementation.

## Agent Dispatch Patterns

Spawn a subagent when:
- A task is purely read-only (search, summarize, scan) — use `gpt-5.4-mini`
- Two or more independent tasks can run in parallel — dispatch both simultaneously
- A task would produce large output the main session doesn't need verbatim

Brief format: task goal + relevant paths/scope + output format + word cap.

## Memory

Use `memory-mcp` as the durable context layer for the same workflows Claude Code uses.

Before substantial implementation, review, debugging, or planning, call `get_context_packet` with the narrowest useful scope:

```text
workspace="ai"
project="memory-mcp"
repo="memory-mcp"       # optional: narrows to this repo within the project
component="<subsystem when clear>"
include_global=true
include_sensitive=false
```

Inspect `context_quality`, `warnings`, `suggested_next_action`, `source_read_policy`, and `source_read_budget_tokens` before reading source. If context is weak or misses the project/component, retry once at project scope before broad source reads.

For source reads:
- `answer_from_packet`: answer from memory and skip source reads.
- `verify_narrowly`: read only the specific snippets needed to confirm the packet.
- `mark_weak_context`: inspect source before answering, but keep reads bounded.

When storing memories with `add_memory`, include `repo="memory-mcp"` in the scope for finer routing.

After meaningful changes, refresh memory with compact, non-sensitive project facts, decisions, commands, constraints, and workflow updates. Never store secrets, credentials, raw logs, transcripts, or sensitive customer data.
