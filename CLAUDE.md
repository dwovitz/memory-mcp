<!-- execution contract -->
## Issue Readiness — Execution Contract

Full contract: `.memory-mcp/issue-contract.md`
Outer-harness execution guidance: `.memory-mcp/outer-run.md`

**Before beginning any implementation**, verify or abort:

1. `status:ready` label present (hard requirement).
2. Readiness score ≥ 0.7 (Phase label, classification label, route label, required sections, no ambiguity markers).
3. `## AI documentation impact` section present and uses a recognized form.
4. Route label present: `route:outer-harness` (default) or `route:inner-harness` (not currently configured — stop and ask if seen).

Fail closed on any missing item. Do not proceed under ambiguity.

## Model Routing (Claude Code)

Use the smallest model that preserves quality. Escalate only when scope or risk requires it.

| Work type | Model | Effort |
|---|---|---|
| File search, log scanning, read-only exploration | Haiku 4.5 | low |
| Documentation and contract updates | Sonnet 4.6 | med |
| Schema or migration changes | Sonnet 4.6 | high |
| Retrieval logic, context assembly, embedding pipeline | Sonnet 4.6 | high |
| Privacy / PII handling, data minimization | Opus 4.8 | high |
| Security review, auth, broad architecture | Opus 4.8 | high |
| Implementation + tests (standard) | Sonnet 4.6 | med–high |

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

**Within-session caching:** After the first `get_context_packet` call in a conversation, save the version token from `get_memory_cache_state` or from the response. On every subsequent `get_context_packet` call in the same session, pass `if_cache_version: <saved_token>`. If the server returns `{"cached": True}`, reuse the previous packet — no tokens consumed. The server detects memory changes automatically and returns a fresh packet when the version changes.

For source reads:
- `answer_from_packet`: answer from memory and skip source reads.
- `verify_narrowly`: read only the specific snippets needed to confirm the packet.
- `mark_weak_context`: inspect source before answering, but keep reads bounded.

When storing memories with `add_memory`, include `repo="memory-mcp"` in the scope for finer routing.

### Entity Graph Tools

```
upsert_entity(entity_type, name, description?, properties?, workspace?, project?, repo?)
```
Idempotent create/update an entity node by `(entity_type, name)`.

```
link_entities(from_type, from_name, to_type, to_name, relationship_type, workspace?, project?, repo?)
```
Idempotent directed edge between two entities.

```
traverse_entity_graph(start_type, start_name, depth?, workspace?, project?, repo?)
```
BFS traversal — returns nodes, edges, and associated memories.

```
get_related_memories(entity_type, name, workspace?, project?, repo?, limit?)
```
Memories linked to a specific entity.

### Code Citations

`search_memory` accepts a `cited_path` filter — narrows results to memories that cite a specific source file path. The two-pass entity-matching classifier improves entity deduplication and match confidence on retrieval.

After meaningful changes, refresh memory with compact, non-sensitive project facts, decisions, commands, constraints, and workflow updates. Never store secrets, credentials, raw logs, transcripts, or sensitive customer data.

## Subagent Model Routing

See the full model/effort table in the `## Model Routing (Claude Code)` section above.

For subagent dispatch: use Haiku for read-only work (capped output), Sonnet for implementation, Opus only when Sonnet is insufficient for architecture or privacy/security scope.

If the active client does not expose per-agent model selection, keep the default model and preserve the read-only/capped-output discipline.

## Agent Dispatch Patterns

Spawn a subagent when:
- A task is purely read-only search, summarization, or log scanning.
- Two or more independent tasks can run in parallel.
- A task would produce large output the main session does not need verbatim.

Always brief subagents with the task goal, relevant paths or search terms, output format, word cap, and whether they are read-only or may edit.
