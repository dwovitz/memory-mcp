# memory-mcp

Local-first personal memory MCP server for Windows.

`memory-mcp` stores structured personal context in PostgreSQL with pgvector,
supports hybrid retrieval over structured filters and full text, synthesizes
compact LLM-ready context packets, and exposes the system through a local MCP
stdio server.

For agent-client setup across Cursor, GitHub Copilot, Codex, and Claude Code,
see [CLIENT_SETUP_README.md](CLIENT_SETUP_README.md).

## Documentation

- [Documentation index](docs/README.md)
- [Goals](docs/GOALS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Agent workflow](docs/AGENT_WORKFLOW.md)

The current implementation includes:

- Dockerized PostgreSQL with pgvector and Windows bind-mount persistence.
- SQLAlchemy database connection layer and Alembic migrations.
- Structured memory schema with entities, memories, tags, relationships,
  retrieval profiles, context packets, provenance links, and pruning logs.
- Realistic synthetic seed data.
- Repository and service layers for core CRUD operations.
- Hybrid retrieval over filters, tags, full text, confidence, recency, scope,
  and `applies_to`.
- Context packet synthesis and pruning/compression services.
- MCP tools for adding, searching, summarizing, and pruning memory.

## Requirements

- Windows with PowerShell
- Docker Desktop for Windows
- Python 3.12+
- Git

Check Python before installing:

```powershell
python --version
```

## Quick Start Checklist

Run from the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Select-String -Path .env -Pattern '^POSTGRES_PASSWORD=\S+' -Quiet)) {
  $password = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
  (Get-Content .env) -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$password" | Set-Content .env
}
New-Item -ItemType Directory -Force C:\ai\memory-postgres-data
python -m pip install -e ".[dev]"
docker compose up -d postgres
docker compose ps
alembic upgrade head
python scripts/seed_data.py
python scripts/test_db_connection.py
python -m pytest
memory-mcp
```

Wait for `docker compose ps` to show the `postgres` service as `healthy`
before running migrations, seed scripts, or the MCP server.

## Configuration

Copy the example environment file:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Select-String -Path .env -Pattern '^POSTGRES_PASSWORD=\S+' -Quiet)) {
  $password = [Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
  (Get-Content .env) -replace '^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$password" | Set-Content .env
}
```

If `.env` already exists, review it instead of overwriting it. It may contain
your local port, credentials, or `PGDATA_HOST_PATH`.

Default values:

```text
POSTGRES_DB=memory_mcp
POSTGRES_HOST=127.0.0.1
POSTGRES_USER=memory_mcp
POSTGRES_PASSWORD=<required local password>
POSTGRES_PORT=5432
POSTGRES_BIND_HOST=127.0.0.1
PGDATA_HOST_PATH=C:\ai\memory-postgres-data
MEMORY_MCP_ENABLE_MUTATION_TOOLS=false
MEMORY_MCP_ENABLE_SENSITIVE_TOOLS=false
```

`PGDATA_HOST_PATH` is the Windows host directory used for durable PostgreSQL
files. Keep it outside the repository. `POSTGRES_BIND_HOST=127.0.0.1` keeps
PostgreSQL reachable only from the local machine by default.

MCP safety gates are disabled by default:

- `MEMORY_MCP_ENABLE_MUTATION_TOOLS=true` enables `add_memory`,
  `archive_memory`, `supersede_memory`, and `run_pruning_pass`.
- `MEMORY_MCP_ENABLE_SENSITIVE_TOOLS=true` enables `include_sensitive=true`
  reads and sensitive/private write echo.

## Windows Docker Database

Create the persistent data folder:

```powershell
New-Item -ItemType Directory -Force C:\ai\memory-postgres-data
```

Start PostgreSQL:

```powershell
docker compose up -d postgres
docker compose ps
```

The compose file uses:

- Image: `pgvector/pgvector:pg16`
- Restart policy: `unless-stopped`
- Port: `${POSTGRES_BIND_HOST:-127.0.0.1}:${POSTGRES_PORT:-5432}:5432`
- Bind mount: `${PGDATA_HOST_PATH}:/var/lib/postgresql/data`
- PostgreSQL internal data directory:
  `/var/lib/postgresql/data/pgdata`
- Healthcheck: `pg_isready`

Docker Desktop notes:

- Docker Desktop must be running before `docker compose` commands.
- If Docker prompts for file sharing permissions, allow access to the drive
  containing `C:\ai\memory-postgres-data`.
- Do not store PostgreSQL data inside the repository.
- Keep `POSTGRES_BIND_HOST=127.0.0.1` unless another machine on your LAN must
  connect directly to PostgreSQL. If you opt into LAN access, use a strong
  password and restrict access with Windows Firewall.
- Enable Docker Desktop's "Start Docker Desktop when you sign in" setting if
  you want PostgreSQL available after Windows login.
- Because the service uses `restart: unless-stopped`, Docker Desktop will
  restart the existing PostgreSQL container when Docker starts, as long as the
  container still exists and was not explicitly stopped.
- Use `docker compose up -d postgres` to create/start the autostarting
  container. Use `docker compose stop postgres` only when you intentionally do
  not want it to restart automatically until you start it again.
- `docker compose down` removes the container. The database files persist in
  the host-mounted folder, but there is no container left to autostart until
  you run `docker compose up -d postgres` again.
- Deleting `C:\ai\memory-postgres-data` deletes the database.

### At-Rest Protection

The PostgreSQL bind mount contains personal facts, preferences, medications,
and evidence in local database files. Treat `C:\ai\memory-postgres-data` as
sensitive data:

- Prefer a BitLocker-protected Windows drive.
- Keep NTFS permissions limited to your Windows user account.
- Do not place the folder in OneDrive, Dropbox, Google Drive, or another sync
  folder unless you intentionally want that data copied.
- Include or exclude the folder from backups deliberately.
- Deleting the folder is a destructive database wipe.

## Python Setup

Install runtime and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Runtime dependencies include SQLAlchemy, psycopg, Alembic, python-dotenv, and
the Python MCP SDK. Development dependencies currently add pytest.

Test the database connection after PostgreSQL is healthy:

```powershell
python scripts/test_db_connection.py
```

The connection test loads `.env`, creates a SQLAlchemy engine, runs
`SELECT 1`, and disposes the engine. It does not create schema.

## Migration Flow

Apply all migrations:

```powershell
alembic upgrade head
```

Check the current database revision:

```powershell
alembic current
```

Rollback all project migrations if you intentionally want an empty schema:

```powershell
alembic downgrade base
```

Alembic requires a real `.env` file with PostgreSQL settings. Migration startup
fails fast instead of silently falling back to default credentials.

### Schema Overview

- `entities` stores named subjects such as people, medications, apps,
  projects, media items, genres, devices, and services.
- `memories` stores the main memory records with content, summary, evidence,
  confidence, sensitivity, status lifecycle, `applies_to`, timestamps,
  superseding fields, and a nullable pgvector embedding placeholder.
- `memory_tags` stores lifecycle-aware tags for memories.
- `relationships` stores typed links between entities, including evidence and
  superseding support.
- `retrieval_profiles` stores named retrieval configuration records as JSONB.
- `context_packets` stores compact synthesized context snapshots.
- `context_packet_memories` stores foreign-key-backed provenance from context
  packets to source memories.
- `pruning_log` records pruning and compression decisions without deleting
  important evidence.

### Retrieval Indexes

- B-tree indexes support ID lookups, joins, lifecycle filters, exact filters,
  and recency ordering.
- Composite B-tree indexes support common retrieval predicates such as status,
  sensitivity, type, entity, and creation time.
- JSONB GIN indexes support containment filters over `applies_to`, evidence,
  metadata, attributes, aliases, and retrieval profile config.
- A PostgreSQL full-text GIN expression index supports lexical search over
  memory `content` and `summary`.
- The `vector` extension is enabled. HNSW indexing is intentionally deferred
  until the embedding model and vector dimensions are chosen.

The supported retrieval strategy is hybrid: apply structured filters first,
use full-text ranking for lexical matches, combine confidence and recency into
ranking, and reserve vector search for the future embedding pipeline.

## Seed Flow

Run the idempotent seed script after migrations:

```powershell
python scripts/seed_data.py
```

The seed script inserts deterministic synthetic data and can be rerun safely.
It upserts rows instead of duplicating them.

Seed data includes:

- Synthetic people: Alex Rivera as self and Jordan Lee as partner.
- Medication memories for Alex.
- Shows liked and disliked, plus genres and tones.
- Devices and services.
- App and project facts for Codex and `memory-mcp`.
- Coding preferences.
- Explicit and inferred memory examples.
- Archived and superseded lifecycle examples.

Useful seed IDs:

```text
Alex Rivera: 5075e3b1-7881-57ba-98ed-06084fe6f224
Jordan Lee: 2cfe97c2-fb9c-5587-a6d8-37c62b67216f
```

Verify seed counts:

```powershell
docker compose exec postgres psql -U memory_mcp -d memory_mcp -c "SELECT entity_type, count(*) FROM entities WHERE attributes @> '{\"seed\": true}'::jsonb GROUP BY entity_type ORDER BY entity_type;"
docker compose exec postgres psql -U memory_mcp -d memory_mcp -c "SELECT memory_type, status, count(*) FROM memories WHERE metadata @> '{\"seed\": true}'::jsonb GROUP BY memory_type, status ORDER BY memory_type, status;"
```

## MCP Usage

Run the local MCP server over stdio:

```powershell
memory-mcp
```

Equivalent module entry point:

```powershell
python -m memory_mcp.main
```

Configure an MCP-capable client to start that command from this repository's
Python environment. The server uses `.env` for database access, so PostgreSQL
must be running and migrated before the MCP client calls tools.

Security defaults:

- The MCP server assumes a trusted local stdio client.
- Search, preference, media, and context-packet tools return only `normal`
  sensitivity memories by default.
- Mutating MCP tools are disabled unless
  `MEMORY_MCP_ENABLE_MUTATION_TOOLS=true` is set.
- Sensitive and private memories require both
  `MEMORY_MCP_ENABLE_SENSITIVE_TOOLS=true` and `include_sensitive=true`.
- Evidence is omitted by default for high-risk tools and must be requested with
  `include_evidence=true` where supported.
- Memory write tools return minimal metadata by default. Use
  `include_content=true` or `include_evidence=true` only when the MCP client
  should receive echoed write details.
- Tool inputs are bounded to reduce accidental large reads/writes.

### Hierarchical Memory Scope

Use `applies_to.memory_scope` to separate durable memory into layers instead of
keeping one flat bucket per repo:

- Global memory: `memory_scope="global"`
- Workspace memory: `memory_scope="workspace"` with `workspace="<root-name>"`
- Project memory: `memory_scope="project"` with `project="<repo-name>"`
- Component memory: `memory_scope="component"` with `project="<repo-name>"`
  and `component="<subsystem-name>"`

Optional `topic` can further narrow a component, for example `topic="auth"` or
`topic="deployment"`.

The MCP `add_memory` and `supersede_memory` tools now accept optional
`memory_scope`, `workspace`, `project`, `component`, and `topic` arguments so
clients do not need to construct that JSON manually. Retrieval tools
`search_memory`, `get_context_packet`, `list_preferences`, and
`summarize_domain_profile` also accept optional `workspace`, `project`,
`component`, `topic`, and `include_global` arguments.

When hierarchical context is provided, retrieval prefers narrower layers first:

1. component
2. project
3. workspace
4. global

Each layer is capped during merge so a large project or workspace does not dump
all known memory into one packet.

For branch-aware application-development memory, prefer the generic
`scope_path` field when the hierarchy needs more than those four compatibility
layers. `scope_path` is stored in `applies_to` as an ordered list, and retrieval
can walk parent prefixes from the requested scope back toward the root:

```json
{
  "scope_path": [
    "global",
    "user:David",
    "domain:software-development",
    "project:MetroidvaniaGame",
    "repo:unity-client",
    "app:gameplay",
    "module:combat",
    "branch:combat-refactor",
    "feature:attack-buffering"
  ]
}
```

When `scope_path` is supplied to `search_memory`, `get_context_packet`,
`list_preferences`, or `summarize_domain_profile`, retrieval checks the direct
scope first and then inherited parent scopes when `include_inherited` is true.
Lower-scope memories can hide inherited parent facts by storing
`metadata.overrides_memory_ids` through the `overrides_memory_ids` tool input.
This is intended for branch-local changes where a parent memory remains true on
main or another branch but is not current for the requested branch. Optional
`valid_from` and `valid_to` values in `applies_to` exclude memories outside
their validity window during scoped-path retrieval.

Available MCP tools:

- `add_memory`
- `archive_memory`
- `supersede_memory`
- `search_memory`
- `get_context_packet`
- `list_preferences`
- `list_liked_media`
- `list_disliked_media`
- `list_medications_for_person`
- `summarize_domain_profile`
- `run_pruning_pass`

Example tool inputs are in `examples/mcp_tools.md`.

### Example MCP Queries

Search show-related memories:

```json
{
  "tool": "search_memory",
  "arguments": {
    "query": "shows Alex likes and dislikes",
    "memory_types": ["entertainment_preference", "inferred_preference"],
    "scope": "entertainment",
    "include_sensitive": false,
    "limit": 5
  }
}
```

List liked science-fiction media:

```json
{
  "tool": "list_liked_media",
  "arguments": {
    "genre": "Science fiction",
    "person_id": "5075e3b1-7881-57ba-98ed-06084fe6f224",
    "limit": 10
  }
}
```

List medications for Alex:

```json
{
  "tool": "list_medications_for_person",
  "arguments": {
    "person_id": "5075e3b1-7881-57ba-98ed-06084fe6f224",
    "include_archived": false,
    "include_sensitive": true,
    "include_evidence": false
  }
}
```

Generate a compact context packet:

```json
{
  "tool": "get_context_packet",
  "arguments": {
    "request": "What should I remember while changing auth in memory-mcp?",
    "workspace": "ai-root",
    "project": "memory-mcp",
    "component": "mcp-tools",
    "topic": "auth",
    "include_evidence": false,
    "include_sensitive": false,
    "max_memories": 8,
    "max_tokens": 1200
  }
}
```

Generate a branch-aware feature context packet:

```json
{
  "tool": "get_context_packet",
  "arguments": {
    "request": "Current architecture context for attack buffering",
    "scope_path": [
      "global",
      "user:David",
      "domain:software-development",
      "project:MetroidvaniaGame",
      "repo:unity-client",
      "app:gameplay",
      "module:combat",
      "branch:combat-refactor",
      "feature:attack-buffering"
    ],
    "include_inherited": true,
    "max_memories": 8,
    "max_tokens": 1200
  }
}
```

Store a reusable global security rule:

```json
{
  "tool": "add_memory",
  "arguments": {
    "memory_type": "coding_preference",
    "summary": "Default to security-first review on auth-related changes.",
    "content": "Across projects, treat auth, permissions, secret handling, and audit logs as high-risk areas and review them conservatively.",
    "memory_scope": "global",
    "applies_to": {
      "scope": "development",
      "domain": "security"
    },
    "tags": ["security", "review"]
  }
}
```

Store a project-scoped rule:

```json
{
  "tool": "add_memory",
  "arguments": {
    "memory_type": "project_fact",
    "summary": "Browser auth uses cookie sessions.",
    "content": "In memory-mcp, browser-facing auth should use secure cookie sessions rather than browser-stored JWTs.",
    "memory_scope": "project",
    "project": "memory-mcp",
    "applies_to": {
      "scope": "development",
      "domain": "security"
    },
    "tags": ["security", "auth"]
  }
}
```

Store a component-scoped rule inside a larger repo:

```json
{
  "tool": "add_memory",
  "arguments": {
    "memory_type": "project_fact",
    "summary": "Auth component uses server sessions.",
    "content": "In payments-api, the auth component uses server-side sessions and cookie-based browser auth.",
    "memory_scope": "component",
    "workspace": "corp-root",
    "project": "payments-api",
    "component": "auth",
    "topic": "sessions",
    "applies_to": {
      "scope": "development",
      "domain": "security"
    },
    "tags": ["security", "auth"]
  }
}
```

Archive an obsolete memory by ID:

```json
{
  "tool": "archive_memory",
  "arguments": {
    "memory_id": "00000000-0000-0000-0000-000000000000"
  }
}
```

Supersede a stale project memory with an updated replacement:

```json
{
  "tool": "supersede_memory",
  "arguments": {
    "memory_id": "00000000-0000-0000-0000-000000000000",
    "memory_type": "project_fact",
    "summary": "Repo is now a Flask task tracker.",
    "content": "memory-test is now a small Flask task-tracker application with a thin route/service split.",
    "memory_scope": "project",
    "project": "memory-test",
    "applies_to": {
      "scope": "development"
    },
    "tags": ["project", "flask"]
  }
}
```

## Context Packets

`ContextSynthesisService` classifies a request, searches only relevant memory
domains, prefers summaries, includes details only when needed, and can include
itemized evidence.

Packet output includes:

- Preferences
- Facts
- Episodic context
- Optional evidence
- Before/after token estimates
- Optional token budget enforcement through `max_tokens`

Examples with token reduction are in `examples/context_packet_synthesis.md`.

## Pruning And Compression

`PruningService` reduces noise without physically deleting memory rows.

Rules:

- Merge duplicate active memories by superseding lower-value copies.
- Archive stale low-value memories.
- Decay weak inferred memories over time.
- Promote compact summaries when useful.
- Preserve important evidence for sensitive, private, medication, personal,
  project, app, pinned, or explicit-source memories.
- Write every pruning action to `pruning_log`.

Run through MCP with `run_pruning_pass`, or from Python by using
`memory_mcp.pruning.PruningService`.

## Tests

Run the test suite:

```powershell
python -m pytest
```

Run static syntax validation without external services:

```powershell
python -m compileall src scripts migrations tests
```

The tests exercise repository behavior, service behavior, retrieval statement
construction, context synthesis, pruning logic, and MCP helper serialization.
Database-backed runtime validation still requires Docker PostgreSQL.

## End-To-End Validation Flow

This flow validates setup, migrations, seed data, MCP usage, and bind-mounted
persistence.

1. Start the database:

```powershell
docker compose up -d postgres
docker compose ps
```

2. Run migrations:

```powershell
alembic upgrade head
alembic current
```

3. Seed data:

```powershell
python scripts/seed_data.py
```

4. Run the MCP server in a dedicated terminal.

Terminal A:

```powershell
memory-mcp
```

Keep this terminal open while testing MCP tools. The process uses stdio, so it
waits for an MCP client and does not return to the PowerShell prompt.

5. Query shows from your MCP-capable client.

Use tool `search_memory` with these arguments:

```json
{
  "query": "shows Alex likes and dislikes",
  "memory_types": ["entertainment_preference", "inferred_preference"],
  "scope": "entertainment",
  "limit": 5
}
```

Expected seed results include `Likes Severance`, `Dislikes sustained bleak
zombie tone`, and `Inferred sci-fi preference`.

6. Query medications from your MCP-capable client.

Use tool `list_medications_for_person` with these arguments:

```json
{
  "person_id": "5075e3b1-7881-57ba-98ed-06084fe6f224",
  "include_archived": false,
  "include_sensitive": true,
  "include_evidence": false
}
```

Expected seed results include cetirizine and magnesium example memories.

7. Generate a context packet from your MCP-capable client.

Use tool `get_context_packet` with these arguments:

```json
{
  "request": "What should I remember while coding memory-mcp?",
  "include_evidence": false,
  "include_sensitive": false,
  "max_memories": 8
}
```

Expected output includes project facts, Codex app knowledge, coding
preferences, and token reduction estimates.

8. Stop the MCP server.

Return to Terminal A and press `Ctrl+C`. Stop the MCP process before destroying
the database container so connection errors from the still-running server do
not obscure the persistence check.

9. Destroy the DB container without deleting the bind-mounted data.

Terminal B:

```powershell
docker compose down
```

10. Recreate the DB container:

```powershell
docker compose up -d postgres
docker compose ps
```

11. Verify persistence:

```powershell
docker compose exec postgres psql -U memory_mcp -d memory_mcp -c "SELECT count(*) AS memories FROM memories;"
docker compose exec postgres psql -U memory_mcp -d memory_mcp -c "SELECT summary FROM memories WHERE memory_type = 'medication' ORDER BY summary;"
```

The data persists because PostgreSQL writes its database files into
`C:\ai\memory-postgres-data`, which survives container removal.

### Disposable Persistence Check

If you want a minimal isolated persistence proof, insert and later remove a
temporary table:

```powershell
docker compose exec postgres psql -U memory_mcp -d memory_mcp -c "CREATE TABLE IF NOT EXISTS persistence_test (id int PRIMARY KEY, note text); INSERT INTO persistence_test (id, note) VALUES (1, 'persisted') ON CONFLICT (id) DO UPDATE SET note = EXCLUDED.note;"
docker compose down
docker compose up -d postgres
docker compose ps
docker compose exec postgres psql -U memory_mcp -d memory_mcp -c "SELECT * FROM persistence_test;"
docker compose exec postgres psql -U memory_mcp -d memory_mcp -c "DROP TABLE persistence_test;"
```

## Troubleshooting

- Python install fails with `requires-python >=3.12`: install or activate
  Python 3.12+ before running `pip install -e`.
- `docker compose up` complains about `PGDATA_HOST_PATH`: copy `.env.example`
  to `.env` and make sure `PGDATA_HOST_PATH` points to an existing Windows
  folder.
- `docker compose up` complains about `POSTGRES_PASSWORD`: set a non-empty
  local password in `.env`.
- PostgreSQL commands fail immediately after startup: wait until
  `docker compose ps` shows `healthy`.
- Port `5432` is already in use: change `POSTGRES_PORT` in `.env`, then restart
  Docker Compose.
- Alembic says `.env` is missing: create `.env` in the repository root.
- `memory-mcp` command is not found: rerun `python -m pip install -e ".[dev]"`
  in the active Python environment.
- MCP tools cannot connect to the database: verify Docker is running,
  migrations are applied, and `.env` points at the exposed PostgreSQL port.
- MCP searches do not return medication or private data: pass
  `include_sensitive=true` for trusted local requests that need sensitive or
  private memories.
- Seed queries return no rows: run `alembic upgrade head` first, then rerun
  `python scripts/seed_data.py`.
- Persistence check fails after `docker compose down`: confirm you did not
  delete `C:\ai\memory-postgres-data` and that `.env` still points to the same
  `PGDATA_HOST_PATH`.

## Project Structure

- `src/memory_mcp/` - Python package source.
- `src/memory_mcp/db/` - SQLAlchemy engine and session helpers.
- `src/memory_mcp/models/` - SQLAlchemy models and shared database types.
- `src/memory_mcp/repositories/` - CRUD repository layer.
- `src/memory_mcp/services/` - application services and context synthesis.
- `src/memory_mcp/retrieval/` - hybrid retrieval service.
- `src/memory_mcp/mcp_tools/` - MCP server and tool definitions.
- `src/memory_mcp/pruning/` - pruning and compression service.
- `migrations/` - Alembic environment and versioned migrations.
- `scripts/` - local utility scripts.
- `tests/` - pytest suite.
- `examples/` - MCP and context packet examples.
