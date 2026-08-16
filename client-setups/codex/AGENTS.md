# memory-mcp Workflow

Use the `memory-mcp` MCP server for durable project memory.

## Second Brain Is the Source of Truth

This workspace is a second brain. For user-specific facts, preferences, ratings,
watch history, and other personal context, first locate the canonical record in
the local wiki (normally `ai-os/.aios-wiki/`) and follow that record's storage
policy. Do not treat `memory-mcp` as a replacement for the wiki.

- Before writing a chat-reported personal fact to `memory-mcp`, inspect the
  relevant wiki index or topic page for a canonical destination and any
  `storage_policy` declaration.
- If a wiki record says it is local-only or not for `memory-mcp`, update that
  record and do not create a duplicate memory. If a duplicate was created in
  error, archive it.
- For chat-reported entertainment ratings, append to
  `ai-os/.aios-wiki/private/entertainment/david/show-ratings.md` unless its
  storage policy changes. Record only the stated rating and applicable scope
  (for example, seasons watched); do not infer extra preferences.
- Use `memory-mcp` to retrieve wiki-derived context or to store a fact only
  when the wiki explicitly permits that synchronization.

## Retrieval

Before substantial implementation, review, debugging, or planning, call
`get_context_packet` with the narrowest useful scope:

```text
workspace="ai"
project="<repo-name>"
repo="<repo-name>"       # optional: narrows within a multi-repo project
component="<subsystem when clear>"
include_global=true
include_sensitive=false
max_memories=8
max_tokens=1200
```

Inspect `context_quality`, `warnings`, `suggested_next_action`,
`source_read_policy`, and `source_read_budget_tokens` before reading source.

**Within-session caching:** After the first `get_context_packet` call in a
conversation, save the version token from `get_memory_cache_state` or from the
response. On every subsequent `get_context_packet` call in the same session,
pass `if_cache_version: <saved_token>`. If the server returns `{"cached": True}`,
reuse the previous packet — no tokens consumed. The server detects memory changes
automatically and returns a fresh packet when the version changes.

## Source Read Policy

Apply `source_read_policy` from the packet before reading any source:

- `answer_from_packet`: answer from memory; skip source reads.
- `verify_narrowly`: read only the specific snippets needed to confirm the packet;
  stay within `source_read_budget_tokens`.
- `mark_weak_context`: inspect source before answering, but keep reads bounded.

## Memory Refresh

After meaningful project changes, refresh memory with compact, non-sensitive
facts when mutation tools are enabled. Report `project_memory_refreshed: yes/no`
in the final response when relevant.

## Code Exploration — Graph First

Use code-review-graph MCP tools before grep or file reads:

- `semantic_search_nodes` or `query_graph` for symbols, imports, callers, callees, and tests.
- `get_impact_radius` before edits that may affect callers or dependents.
- `detect_changes` plus `get_review_context` for code review.
- `get_architecture_overview` for architecture questions.

Fall back to file reads only when the graph does not cover what you need or the graph tool is unavailable. If unavailable, state that and keep reads bounded.

## Model Routing

When spawning Codex subagents, use the smallest model that preserves quality:

| Task type | Model |
|-----------|-------|
| File search, codebase exploration, log scanning | `gpt-5.4-mini` with low/medium reasoning |
| Implementation, editing code, writing tests | `gpt-5.4` or inherit current model |
| Architecture decisions, complex debugging | `gpt-5.5` with high/xhigh reasoning |

- `gpt-5.4-mini` subagents are read-only only.
- Always cap `gpt-5.4-mini` briefs: "report in under 150 words" or "return a structured list only".
- If a listed model is unavailable, use the closest available smaller model for read-only work and the inherited model for implementation.

## Entity Graph Tools

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

## Code Citations

`search_memory` accepts a `cited_path` filter — narrows results to memories that cite a specific source file path. The two-pass entity-matching classifier improves entity deduplication and match confidence on retrieval.

## Agent Dispatch Patterns

Spawn a subagent when:
- A task is purely read-only search, summarization, or log scanning.
- Two or more independent tasks can run in parallel.
- A task would produce large output the main session does not need verbatim.

Always brief subagents with the task goal, relevant paths or search terms, output format, word cap, and whether they are read-only or may edit.
