<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.

## Memory

Use `memory-mcp` as the durable context layer for the same workflows Codex uses.

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

## Model Routing

When dispatching Claude Code subagents, use the smallest model that preserves quality:

- File search, codebase exploration, log scanning: Haiku, read-only, capped output.
- Implementation, editing code, writing tests: Sonnet or inherited default.
- Architecture decisions, complex debugging, deep reasoning: Opus only when Sonnet is insufficient.

If the active client does not expose per-agent model selection, keep the default model and preserve the same read-only/capped-output subagent discipline.

## Agent Dispatch Patterns

Spawn a subagent when:
- A task is purely read-only search, summarization, or log scanning.
- Two or more independent tasks can run in parallel.
- A task would produce large output the main session does not need verbatim.

Always brief subagents with the task goal, relevant paths or search terms, output format, word cap, and whether they are read-only or may edit.
