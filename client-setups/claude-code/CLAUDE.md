# memory-mcp Workflow

Use the `memory-mcp` MCP server for durable project memory across coding sessions.

## Before Substantial Work

Before brainstorming, planning, debugging, executing plans, or reviewing code — call `get_context_packet` first:

```
get_context_packet(
  request="<what you're about to do>",
  workspace="ai",          # or your workspace root name
  project="<repo-name>",   # e.g. "memory-mcp", "ai-os-discord"
  repo="<repo-name>",      # optional; narrows within a multi-repo project
  component="<subsystem>"  # optional — omit if not focused on one subsystem
)
```

Inspect the response fields before reading source files:
- `context_quality` — `strong | moderate | weak`
- `suggested_next_action` — what the server recommends doing next
- `source_read_policy` — `answer_from_packet | verify_narrowly | mark_weak_context`
- `source_read_budget_tokens` — how many tokens of source reading are budgeted

## MCP Tools

### Retrieval

```
search_memory(query, memory_scope?, workspace?, project?, component?, topic?, memory_type?, include_sensitive?, limit?)
```
Searches memory records and returns compact matching entries.

```
get_context_packet(request, workspace?, project?, repo?, component?, topic?, include_global?, include_sensitive?, max_memories?, max_tokens?, if_cache_version?)
```
Builds a task-specific packet with preferences, facts, checkpoints, quality diagnostics, cache metadata, and source-read guidance.

```
get_memory_cache_state()
```
Returns cache metadata for cache-aware retrieval.

### Writing

```
add_memory(summary, content, memory_type?, memory_scope?, workspace?, project?, repo?, component?, topic?, applies_to?, tags?, confidence?, sensitivity?)
```
Adds a memory when mutation tools are enabled.

```
supersede_memory(memory_id, summary?, content?, reason?, tags?, confidence?)
```
Replaces stale memory content with an updated version.

```
archive_memory(memory_id)
```
Archives obsolete memory.

### Domain Helpers

```
list_preferences(domain?, project?, include_sensitive?)
```

```
list_liked_media(person_id?, domain?, limit?)
```

```
list_disliked_media(person_id?, domain?, limit?)
```

```
summarize_domain_profile(domain, person_id?, project?, include_sensitive?)
```

Sensitive helpers are disabled unless explicitly enabled:

```
list_medications_for_person(person_id, include_evidence?)
```

Maintenance:

```
run_pruning_pass(dry_run?, memory_scope?, workspace?, project?, older_than_days?)
```

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

## Scopes

Use `memory_scope="global"` for universal rules, `workspace` for decisions spanning multiple repos, `project` for product/program facts, `repo` for repository-local facts, and `component` for subsystem facts. Always pass `workspace`, `project`, and/or `repo` when saving scoped memories.

## Source-Read Discipline

Use `source_read_policy` from the context packet:
- `answer_from_packet` — memory is sufficient, skip source reads
- `verify_narrowly` — read only what's needed to confirm 1–2 specific facts
- `mark_weak_context` — inspect source before answering; memory is sparse

## After Meaningful Work

Refresh memory with durable, non-sensitive facts:
- Architecture decisions (`memory_type="architecture_decision"`)
- Non-obvious commands or workflows (`memory_type="project_rule"` or `memory_type="workflow_location"`)
- Environment constraints (`memory_type="project_fact"`)
- Bugs with root cause (`memory_type="project_fact"`)
- Confirmed workflow preferences (`memory_type="coding_preference"`)

Do **not** save: speculation, code-derivable facts, `<private>` content, secrets, or credentials.

Report `project_memory_refreshed: yes/no` in task closeout.

## Code Exploration — Graph First

Use code-review-graph MCP tools before Grep/Glob/Read:

- `semantic_search_nodes` or `query_graph` for symbols, imports, callers, callees, and tests.
- `get_impact_radius` before edits that may affect callers or dependents.
- `detect_changes` plus `get_review_context` for code review.
- `get_architecture_overview` for architecture questions.

Fall back to file reads only when the graph does not cover what you need or the graph tool is unavailable. If unavailable, state that and keep reads bounded.

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
