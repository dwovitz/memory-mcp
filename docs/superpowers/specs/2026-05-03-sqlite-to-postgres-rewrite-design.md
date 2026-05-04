# memory-mcp Rewrite Design
**Date:** 2026-05-03
**Status:** Awaiting user approval

---

## 1. Context and Goal

The current `memory-mcp` server stores personal and project memory in PostgreSQL via Docker, with a complex schema (entities, relationships, medications, media, audit logs, auth layers) and 12 MCP tools tuned for a personal-life memory model.

The goal is to refactor it into a practical, token-efficient memory layer for coding ecosystems: multiple repos worked on together as one workspace, shared by agents across a local machine and a shared work MCP server. The new design retains PostgreSQL (the right backend for concurrent shared access), simplifies the schema to what coding agents actually need, and adds two-stage progressive retrieval to reduce context size.

The existing Docker + PostgreSQL setup at home is kept. The work server runs the same stack. No SQLite. No dual-backend complexity.

---

## 2. What Changes vs. What Stays

### Stays
- PostgreSQL via Docker Compose
- SQLAlchemy 2 + psycopg + Alembic
- FastMCP (mcp package) server pattern
- pyproject.toml / hatchling / pytest
- `get_context_packet` tool (benchmarked and proven)
- Benchmark infrastructure (`benchmarks/`, `cases.json`, `prompts/`, `results/`)

### Removed
- Entities, relationships, medications, media lists tables
- Auth layer (`auth/`)
- Audit logging (`audit/`)
- Cache validation (`get_memory_cache_state`)
- `scope_path` hierarchical tree (replaced by flat three-level scope)
- 12 old MCP tools → replaced by 9 new tools
- `.env`-based config → supplemented by `~/.memory-mcp/config.json`

### Added
- Simplified schema: `memories_v2`, `projects` tables
- Three-level scope: `global | workspace | project`
- `workspace_id` field alongside `project_id`
- Two-stage retrieval: slim search → selective deep fetch
- 8 new MCP tools + retained `get_context_packet` = 9 tools total
- CLI: 11 subcommands via argparse
- Migration script: old schema → new schema (legacy tables preserved with `_legacy` suffix)
- HTTP/SSE transport support for shared work server
- Privacy: `<private>` block stripping + secret detection
- `~/.memory-mcp/config.json` for global config
- Project + workspace auto-detection
- Import/export (JSON and Markdown)
- `docs/AGENT_MEMORY_POLICY.md`

---

## 3. Scope Model

Three scopes, applied consistently across all tools:

| Scope | Meaning | Example |
|---|---|---|
| `global` | Machine-wide. Personal preferences, universal coding rules. | "Always write tests before implementation." |
| `workspace` | Cross-repo ecosystem. How repos relate, shared patterns, ecosystem-wide decisions. | "The ai workspace uses a shared auth library across all repos." |
| `project` | One repo. Its architecture, commands, active bugs, checkpoints. | "memory-mcp uses FastMCP with stdio transport." |

**Workspace detection:** walk up from `cwd`, find the highest ancestor directory that contains multiple child directories with `.git` folders. That is the workspace root. Its folder name becomes the workspace name. If no such parent exists, the nearest `.git` root is the project root with no workspace.

**Project ID generation:** deterministic. SHA-256 of `(git_remote_url or "") + normalized_root_path`, truncated to 16 hex chars. Stored in `projects` with the friendly folder name.

**Workspace ID generation:** same — SHA-256 of normalized workspace root path.

**Search scope order:** when searching inside a project, results are returned from all three levels simultaneously, ranked by `ts_rank` score × scope weight (project=1.0, workspace=0.8, global=0.6) × recency decay. No separate calls needed.

---

## 4. Schema

### New tables (added via Alembic migration `0002_memories_v2.py`)

```sql
CREATE TABLE projects (
    id          TEXT PRIMARY KEY,          -- 16-char hex hash
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'project',  -- 'workspace' | 'project'
    root_path   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata    JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE memories_v2 (
    id            TEXT PRIMARY KEY,        -- random UUID (hex, no dashes)
    title         TEXT NOT NULL,
    summary       TEXT NOT NULL,
    details       TEXT,
    kind          TEXT NOT NULL DEFAULT 'note',
    scope         TEXT NOT NULL DEFAULT 'global',
    workspace_id  TEXT REFERENCES projects(id),
    project_id    TEXT REFERENCES projects(id),
    tags          JSONB NOT NULL DEFAULT '[]',
    source        TEXT,
    confidence    REAL NOT NULL DEFAULT 1.0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    supersedes_id TEXT REFERENCES memories_v2(id),
    metadata      JSONB NOT NULL DEFAULT '{}'
);

-- FTS index (PostgreSQL full-text, GIN)
CREATE INDEX memories_v2_fts_idx ON memories_v2
  USING GIN (to_tsvector('english',
    title || ' ' || summary || ' ' || coalesce(details, '') || ' ' ||
    coalesce(tags::text, '')
  ));

-- Supporting indexes
CREATE INDEX memories_v2_scope_idx ON memories_v2 (scope, project_id, workspace_id);
CREATE INDEX memories_v2_kind_idx  ON memories_v2 (kind);
CREATE INDEX memories_v2_time_idx  ON memories_v2 (created_at DESC);
```

**`kind` values:** `preference | decision | checkpoint | architecture | bug | command | environment | workflow | note`

**`scope` values:** `global | workspace | project`

### Old tables
Renamed to `memories_legacy`, `entities_legacy`, `relationships_legacy`, etc. in the same migration. Not dropped until explicitly verified and cleaned up.

---

## 5. Two-Stage Retrieval

All read paths use two stages:

**Stage 1 — slim search (cheap)**
```sql
SELECT id, title, summary, kind, scope, workspace_id, project_id, tags, created_at,
       ts_rank(to_tsvector('english', title||' '||summary||' '||coalesce(details,'')),
               plainto_tsquery('english', :query)) AS score
FROM memories_v2
WHERE to_tsvector(...) @@ plainto_tsquery('english', :query)
  AND scope = ANY(:scopes)
ORDER BY score DESC, created_at DESC
LIMIT :limit;
```
Returns compact rows. No `details`. Fast.

**Stage 2 — deep fetch (selective)**
```sql
SELECT * FROM memories_v2 WHERE id = ANY(:ids);
```
Called only for IDs selected after stage 1. Returns full records including `details`.

`get_context_packet` runs both stages internally (slim search across all applicable scopes → rank + select top N → deep fetch → synthesize packet). Agents calling `memory.search` directly receive stage 1 output only and decide whether to call `memory.get`.

---

## 6. MCP Tools (9 total)

### New tools

| Tool | Inputs | Returns |
|---|---|---|
| `memory.search` | `query, scope?, workspace_id?, project_id?, tags?, kind?, limit?` | Compact: id, title, summary, tags, kind, scope, score, created_at |
| `memory.get` | `ids: string[]` | Full records for requested IDs only |
| `memory.save` | `title, summary, details?, kind?, scope?, workspace_id?, project_id?, tags?, source?, confidence?` | Saved/updated ID |
| `memory.timeline` | `scope?, workspace_id?, project_id?, since?, limit?, kind?` | Compact chronological list |
| `memory.checkpoint` | `task, state, next_steps?, blockers?, files_changed?, commands_run?, scope?, workspace_id?, project_id?` | Checkpoint ID + resume summary |
| `memory.prune` | `dry_run?, older_than_days?, scope?, workspace_id?, project_id?, tags?, kind?` | Prune report |
| `memory.update` | `id, title?, summary?, details?, tags?, kind?, confidence?` | Updated ID |
| `memory.delete` | `ids: string[]` | Deleted IDs |

### Retained tool (updated internals, same interface)

| Tool | Change |
|---|---|
| `get_context_packet` | Rewired to query `memories_v2` using two-stage retrieval. `workspace` → `workspace_id`, `project` → `project_id`. `component` is treated as an additional keyword appended to the FTS query (not a separate scope level), so component-specific memories surface via relevance rather than a dedicated scope. `source_read_policy`, `context_quality`, `suggested_next_action` preserved in output. |

### `memory.save` deduplication
Before inserting, run a slim search for same-scope/kind memories with similar title tokens (FTS query on title words). If top result score > 0.85, update that record instead of inserting. Return the updated ID with `updated: true`.

### Privacy rules (applied in `memory.save` and `memory.checkpoint`)
1. Strip `<private>…</private>` blocks (regex, case-insensitive, including multiline).
2. Detect and reject saves that match secret patterns: API key formats, bearer tokens, private key headers, `.env` `KEY=VALUE` lines, connection strings with passwords. Return error naming the pattern type, not the value.

---

## 7. CLI (13 subcommands, argparse)

```
memory-mcp init                    Create ~/.memory-mcp/, config.json, run migrations
memory-mcp doctor                  Check DB connection, schema version, config validity
memory-mcp search "query"          Slim search, print to stdout
memory-mcp get <id>                Full record, print to stdout
memory-mcp save --title … --summary … [--scope] [--kind] [--workspace] [--project]
memory-mcp checkpoint --task … --state …
memory-mcp timeline [--scope] [--since] [--limit]
memory-mcp export --format json|markdown
memory-mcp import <file>           Import from prior export, skip duplicate IDs
memory-mcp prune [--dry-run] [--older-than-days N]
memory-mcp migrate-from-legacy [--include-archived] [--dry-run]
memory-mcp drop-legacy             Drop _legacy tables after verifying migration
memory-mcp server [--transport stdio|http] [--port 8080]
```

`memory-mcp server` defaults to `stdio` transport. `--transport http` enables SSE for the shared work server.

---

## 8. Global Config

`~/.memory-mcp/config.json` — created by `memory-mcp init`:

```json
{
  "database_url": "postgresql+psycopg://memory_mcp:password@127.0.0.1:5432/memory_mcp",
  "default_scope": "global",
  "max_search_results": 20,
  "max_summary_chars": 2000,
  "max_details_chars": 10000,
  "enable_workspace_detection": true,
  "ignored_paths": [],
  "ignored_tags": [],
  "log_level": "WARNING"
}
```

Config is loaded in order: `~/.memory-mcp/config.json` → env vars → defaults. Env var `MEMORY_MCP_DATABASE_URL` overrides config file.

---

## 9. Migration from Old Schema

`memory-mcp migrate-from-legacy` (additional CLI subcommand):

1. Rename old tables: `memories → memories_legacy`, `entities → entities_legacy`, etc.
2. Read `memories_legacy` rows.
3. Map fields:
   - `memory_type` → `kind` (mapping table: `coding_preference→preference`, `project_fact→architecture`, `component_summary→architecture`, `project_rule→decision`, `ephemeral_note→note`, etc.)
   - `summary` → `summary`
   - `content` → `details`
   - `applies_to.memory_scope` → `scope` (`global|workspace|project`; `component` maps to `project`)
   - `applies_to.workspace` → look up/create workspace in `projects`, set `workspace_id`
   - `applies_to.project` → look up/create project in `projects`, set `project_id`
   - `memory_tags` rows → aggregate into `tags` JSON array
   - `confidence`, `created_at` → direct
4. Skip `memories_legacy` rows with `status IN ('archived', 'superseded', 'deleted')` unless `--include-archived` flag.
5. Write to `memories_v2`.
6. Report: migrated count, skipped count, unmapped kinds.

`memories_legacy` and other legacy tables are **not dropped** by this command. Run `memory-mcp drop-legacy` explicitly after verifying.

---

## 10. Benchmark Compatibility

`cases.json` memories use old field names (`memory_type`, `applies_to` with workspace/project/component). The benchmark runner seeds memories via `add_memory` (old tool). 

Updates needed:
- Seed step in runner: call `memory.save` instead of `add_memory`, map field names.
- `get_context_packet` tool: update internals to query `memories_v2` but keep external interface identical (same input params, same output structure).
- `cases.json`: no change required — field mapping is handled in the runner seed step.
- Existing `results/` files: unchanged, remain as historical baselines.

---

## 11. Testing

All tests use a real PostgreSQL connection via `pytest` fixture (same Docker instance). No fakes for DB layer.

| File | Covers |
|---|---|
| `tests/test_store.py` | save, search (two-stage), get, timeline, checkpoint, update, delete, dedup |
| `tests/test_privacy.py` | private block stripping, secret detection (parametrized) |
| `tests/test_project_detection.py` | workspace detection, project ID generation, fallback |
| `tests/test_migrations.py` | migration 0002 applies cleanly, legacy tables renamed |
| `tests/test_legacy_migration.py` | old→new field mapping, skipped statuses, kind mapping |
| `tests/test_cli.py` | smoke tests for each CLI subcommand via subprocess |
| `tests/test_mcp_tools.py` | tool registration, round-trip save/search/get/checkpoint |
| `tests/test_export_import.py` | JSON export → import round-trip |
| `tests/test_context_packet.py` | get_context_packet two-stage retrieval, scope ranking |

---

## 12. File Layout (after rewrite)

```
src/memory_mcp/
  config.py              ← load ~/.memory-mcp/config.json + env vars
  detect.py              ← workspace + project detection
  privacy.py             ← private block stripping + secret detection
  db/
    connection.py        ← engine, session_scope (unchanged)
    __init__.py
  store/
    memories.py          ← CRUD + FTS search + dedup on memories_v2
    projects.py          ← project/workspace upsert + ID generation
    __init__.py
  tools/
    server.py            ← FastMCP tool definitions (thin wrappers over store)
    context_packet.py    ← get_context_packet (rewired to memories_v2)
    __init__.py
  cli/
    main.py              ← argparse entry point + subcommands
    __init__.py
  migrate/
    legacy.py            ← old schema → memories_v2 migration logic
    __init__.py
  main.py                ← entry point (delegates to cli or server)
  __init__.py

migrations/
  versions/
    0001_initial_memory_schema.py   ← existing (unchanged)
    0002_memories_v2.py             ← new: add memories_v2, projects, rename legacy

docs/
  AGENT_MEMORY_POLICY.md           ← new
  superpowers/specs/
    2026-05-03-sqlite-to-postgres-rewrite-design.md  ← this file
```

---

## 13. Acceptance Criteria

1. `memory-mcp doctor` passes (DB connected, schema current, config valid).
2. `memory-mcp server` starts on stdio and accepts MCP connections.
3. `memory-mcp server --transport http --port 8080` starts for shared work server.
4. All 9 MCP tools registered and callable.
5. `memory.save` works at global, workspace, and project scope.
6. `memory.search` returns compact results (no details).
7. `memory.get` returns full records.
8. `get_context_packet` returns structured packet using two-stage retrieval.
9. Private blocks stripped; obvious secrets rejected.
10. `memory-mcp migrate-from-legacy` migrates old memories to `memories_v2`.
11. Export/import round-trip works.
12. All tests pass against live Docker PostgreSQL.
13. Benchmarks runnable against new schema (runner seed step updated).
14. `docs/AGENT_MEMORY_POLICY.md` written.
