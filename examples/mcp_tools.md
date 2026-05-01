# MCP Tool Examples

Run the server after installing dependencies and applying migrations:

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
memory-mcp
```

Wait for `docker compose ps` to show `healthy` before running migrations. The
server uses the default MCP stdio transport.

Run `memory-mcp` in the terminal configured by your MCP client. The JSON below
is tool argument input for an MCP-capable client, not PowerShell input to paste
after starting the stdio server. Stop the server with `Ctrl+C` when finished.

Tools return only `normal` sensitivity memories by default. Pass
`include_sensitive: true` only for trusted local requests that need sensitive or
private data.

## add_memory

```json
{
  "memory_type": "coding_preference",
  "content": "Prefer small, reviewable Python changes with clear summaries.",
  "summary": "Prefer small reviewable Python changes.",
  "confidence": 0.95,
  "sensitivity": "normal",
  "applies_to": {"scope": "development"},
  "tags": ["coding", "preference"]
}
```

Branch-scoped memory with a lower-scope override:

```json
{
  "memory_type": "architecture_decision",
  "content": "combat-refactor replaces direct PlayerAttack input polling with InputReader events.",
  "summary": "combat-refactor uses event-driven attack input.",
  "scope_path": [
    "global",
    "user:David",
    "domain:software-development",
    "project:MetroidvaniaGame",
    "repo:unity-client",
    "app:gameplay",
    "module:combat",
    "branch:combat-refactor"
  ],
  "scope_type": "branch",
  "overrides_memory_ids": ["00000000-0000-0000-0000-000000000000"],
  "valid_from": "2026-04-24T00:00:00+00:00",
  "tags": ["architecture", "input", "branch-note"]
}
```

## search_memory

```json
{
  "query": "Python project preferences",
  "memory_types": ["coding_preference", "project_fact"],
  "scope": "development",
  "min_confidence": 0.5,
  "include_sensitive": false,
  "limit": 5
}
```

```json
{
  "query": "attack buffering architecture",
  "scope_path": [
    "global",
    "project:MetroidvaniaGame",
    "repo:unity-client",
    "module:combat",
    "branch:combat-refactor",
    "feature:attack-buffering"
  ],
  "include_inherited": true,
  "memory_types": ["architecture_decision", "workflow_location", "project_rule"],
  "limit": 8
}
```

## get_context_packet

```json
{
  "request": "What should I remember while coding memory-mcp?",
  "workspace": "ai",
  "project": "memory-mcp",
  "include_evidence": false,
  "include_sensitive": false,
  "max_memories": 8,
  "max_tokens": 1200
}
```

Read `context_quality`, `warnings`, `diagnostics.fallback_attempts`,
`suggested_next_action`, `source_read_policy`, and
`source_read_budget_tokens` in the response. A weak project packet means the
client should retry with a broader project scope or record a retrieval miss
before reading large source slices; a usable packet should only trigger focused
snippet verification within the returned budget.

## list_preferences

```json
{
  "domain": "coding",
  "limit": 10
}
```

## list_liked_media

```json
{
  "genre": "Science fiction",
  "limit": 10
}
```

## list_disliked_media

```json
{
  "limit": 10
}
```

## list_medications_for_person

```json
{
  "person_id": "5075e3b1-7881-57ba-98ed-06084fe6f224",
  "include_archived": false,
  "include_sensitive": true,
  "include_evidence": false
}
```

## summarize_domain_profile

```json
{
  "domain": "project",
  "project": "memory-mcp",
  "include_evidence": true,
  "include_sensitive": false
}
```

## run_pruning_pass

```json
{
  "stale_after_days": 180,
  "inference_half_life_days": 90
}
```

## Security Notes

These examples assume trusted local stdio mode. In remote mode, adapters must
set an authenticated principal before invoking tools. Reads require read access
to the requested workspace/project/component, mutation tools require mutation
grants, `include_sensitive=true` requires a sensitive-read grant, and sensitive
or private write echo through `include_content` or `include_evidence` requires a
sensitive-echo grant. Denials should be treated as authorization failures, not
validation errors.
