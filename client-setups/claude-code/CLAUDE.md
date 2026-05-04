# memory-mcp Workflow

Use the `memory` MCP server for durable project memory across coding sessions.

## Before Substantial Work

Before brainstorming, planning, debugging, executing plans, or reviewing code — call `get_context_packet` first:

```
get_context_packet(
  request="<what you're about to do>",
  workspace="ai",          # or your workspace root name
  project="<repo-name>",   # e.g. "memory-mcp", "ai-os-discord"
  component="<subsystem>"  # optional — omit if not focused on one subsystem
)
```

Inspect the response fields before reading source files:
- `context_quality` — `strong | moderate | weak`
- `suggested_next_action` — what the server recommends doing next
- `source_read_policy` — `answer_from_packet | verify_narrowly | mark_weak_context`
- `source_read_budget_tokens` — how many tokens of source reading are budgeted

## The 9 MCP Tools

### Retrieval (two-stage)

**Stage 1 — slim search (no details):**
```
memory_search(query, scope?, workspace_id?, project_id?, kind?, limit?)
```
Returns compact records. Use this before fetching full content.

**Stage 2 — deep fetch:**
```
memory_get(ids: list[str])
```
Returns full records including `details`. Call only for IDs surfaced by search.

**Timeline (no query needed):**
```
memory_timeline(scope?, workspace_id?, project_id?, since?, limit?, kind?)
```
Chronological listing — useful for finding checkpoints to resume from.

### Writing

```
memory_save(title, summary, details?, kind?, scope?, workspace_id?, project_id?, tags?, confidence?)
```
Deduplicates automatically — close title match in the same scope+kind updates instead of inserting.

```
memory_update(id, title?, summary?, details?, tags?, kind?, confidence?)
```

```
memory_delete(ids: list[str])
```

### Session Management

```
memory_checkpoint(task, state, next_steps?, blockers?, files_changed?, commands_run?, scope?, workspace_id?, project_id?)
```
Saves a resumable work checkpoint. Call at the end of long sessions.

```
memory_prune(dry_run=True, older_than_days?, scope?, workspace_id?, project_id?, kind?)
```
Default is dry-run — inspect before deleting.

### Context Synthesis

```
get_context_packet(request, workspace?, project?, component?, workspace_id?, project_id?, max_memories?, max_tokens?)
```
Two-stage internally: slim search → deep fetch of top results → structured packet.
Returns `preferences`, `facts`, `checkpoints`, `context_quality`, `suggested_next_action`, `source_read_policy`, `source_read_budget_tokens`.

## Scopes

| Situation | scope |
|---|---|
| Universal rule for all projects | `global` |
| Decision spanning multiple repos in the ecosystem | `workspace` |
| Fact about one specific repo | `project` |

Always pass `workspace_id` and/or `project_id` when saving `workspace` or `project` scoped memories.

## Source-Read Discipline

Use `source_read_policy` from the context packet:
- `answer_from_packet` — memory is sufficient, skip source reads
- `verify_narrowly` — read only what's needed to confirm 1–2 specific facts
- `mark_weak_context` — inspect source before answering; memory is sparse

## After Meaningful Work

Refresh memory with durable, non-sensitive facts:
- Architecture decisions (`kind=architecture`)
- Non-obvious commands (`kind=command`)
- Environment constraints (`kind=environment`)
- Bugs with root cause (`kind=bug`)
- Confirmed workflow preferences (`kind=preference`)

Do **not** save: speculation, code-derivable facts, `<private>` content, secrets, or credentials.

Report `project_memory_refreshed: yes/no` in task closeout.
