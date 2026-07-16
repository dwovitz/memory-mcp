# Auto-Capture and Distillation

memory-mcp can automatically capture Claude Code session events and distill
them into typed memories without manual `add_memory` calls.

## Architecture

```
Claude Code session
   ├─ PostToolUse hook ─┐
   ├─ UserPromptSubmit ─┼─► HTTP POST /tool/enqueue_observation
   ├─ SessionStart   ───┤        (MCP server, FastMCP HTTP transport)
   └─ SessionEnd     ───┘
                              │
                              ▼
                  Postgres: staging_observations (FOR UPDATE SKIP LOCKED)
                              │
                              ▼
                  distiller worker(s) — Haiku/Sonnet routed
                              │
                              ▼
                  IngestWriter ─► memories table (typed, scoped, deduped)
```

Auto-capture is one of two ingestion paths that share the `IngestWriter`
dedup/supersession primitive. The other is **wiki ingestion**, which projects a
canonical local wiki into provenance-stamped, private-by-default records (and a
deterministic `wiki_document`/`references` entity graph) and reconciles them on
every run — see [wiki_ingestion.md](wiki_ingestion.md). Both paths feed the
combined, provenance-backed retrieval in [retrieval.md](retrieval.md); their
captured/projected memories carry the `metadata.source` provenance that
retrieval surfaces as *why-retrieved* reasons.

Multiple distiller workers can run concurrently; `claim_batch` uses
`SELECT ... FOR UPDATE SKIP LOCKED` so they never collide. UserPromptSubmit
also pulls a `get_context_packet` and injects it into the model context, so
durable knowledge surfaces automatically without the model having to call
`get_context_packet` itself.

## Server-Side Setup

1. `alembic upgrade head` to create `staging_observations`.
2. `docker compose up -d distiller` to start the worker.
3. Ensure the MCP server exposes the FastMCP HTTP transport on the hook URL
   configured below (default `8765`). Set `ANTHROPIC_API_KEY` in the distiller's
   environment and `MEMORY_MCP_ENABLE_MUTATION_TOOLS=true` on the server.

## Client-Side Setup

In `~/.claude/settings.json` (or per-project `.claude/settings.json`):

```json
{
  "hooks": {
    "PostToolUse": [{"command": "python /path/to/memory-mcp/hooks/post_tool_use.py"}],
    "UserPromptSubmit": [{"command": "python /path/to/memory-mcp/hooks/user_prompt_submit.py"}],
    "SessionStart": [{"command": "python /path/to/memory-mcp/hooks/session_start.py"}],
    "SessionEnd": [{"command": "python /path/to/memory-mcp/hooks/session_end.py"}]
  },
  "env": {
    "MEMORY_MCP_HOOK_URL": "http://memory-mcp.local:8765",
    "MEMORY_MCP_WORKSPACE": "ai",
    "MEMORY_MCP_PROJECT": "memory-mcp",
    "MEMORY_MCP_REPO": "memory-mcp"
  }
}
```

Hooks are non-blocking; if the server is unreachable they swallow the
error and return immediately so the user's session is never affected.

## Safety and Bounds

- The server authorizes every enqueue as a write, accepts only the four hook
  event types, rejects known credential patterns, and limits each JSON payload
  to 6,000 characters. Hooks additionally truncate tool input, responses, and
  session summaries before sending them.
- A distiller call handles at most eight observations. It receives only staged,
  bounded observations; raw observations are not stored as durable memories.
- Every promoted memory is private by default, marked `metadata.source:
  auto_capture`, and retains only the staging observation IDs and source event
  types explicitly cited by the distiller. The server validates those IDs and
  requires the exact common cited scope; model output cannot replace that
  provenance, widen a claim's scope, or introduce arbitrary durable-memory
  fields.
- Failed model or promotion calls mark their staging rows as failed for
  observability; hooks remain non-blocking.
- Private auto-captured memories are excluded from normal retrieval and direct
  ID dereferencing unless the caller explicitly requests sensitive content and
  has the server's sensitive-read capability.

## Observability

- Pending queue depth: `SELECT count(*) FROM staging_observations WHERE status='pending';`
- Failed batches: `SELECT id, error_message FROM staging_observations WHERE status='failed' ORDER BY completed_at DESC LIMIT 20;`
- Distillation throughput: distiller logs one INFO line per batch.

## Cost Notes

Routing in `distiller/router.py`:
- Read-only / simple tools (`Read`, `Glob`, `Grep`) → Haiku.
- Anything involving `user_prompt_submit`, `session_end`, payloads
  >10 KB, or write tools (`Edit`, `Write`) → Sonnet.

Adjust `_SIMPLE_TOOLS` and `_SIZE_THRESHOLD_BYTES` in
`src/memory_mcp/distiller/router.py` to tune cost.
