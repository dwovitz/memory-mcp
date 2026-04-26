# memory-mcp Client Setup

This guide covers setup and usage for connecting `memory-mcp` to coding agents.
Use the main [README.md](README.md) for database architecture, migrations, seed
data, and project internals.

Version references below were checked on 2026-04-24. Treat them as tested
baselines, not permanent pins.

## Supported Client Baselines

| Client | Baseline version | Notes |
| --- | --- | --- |
| Cursor | 3.1 latest | Cursor 3.x has the current agent UI and MCP-related workflows. |
| GitHub Copilot for VS Code | Copilot extension 1.388.0, VS Code engine `^1.103.0` | Use the latest VS Code and Copilot Chat; Copilot Chat compatibility follows VS Code closely. |
| OpenAI Codex CLI | `@openai/codex` 0.124.0 | Use the npm package or the Codex app if it exposes MCP config in your environment. |
| Claude Code | `@anthropic-ai/claude-code` 2.1.119 | Supports MCP, skills, and hooks; hooks are optional for this server. |

## Local Server Setup

Run from the repository root:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
New-Item -ItemType Directory -Force C:\ai\memory-postgres-data
python -m pip install -e ".[dev]"
docker compose up -d postgres
docker compose ps
alembic upgrade head
python -m pytest
```

The server runs over stdio:

```powershell
memory-mcp
```

Equivalent module form:

```powershell
python -m memory_mcp.main
```

If a client needs an absolute command path on Windows, use the editable install
entry point:

```text
D:\git\ai\memory-mcp\.venv\Scripts\memory-mcp.exe
```

## MCP Server Configuration

Use one of these command shapes in clients that support local stdio MCP
servers.

Preferred executable form:

```json
{
  "mcpServers": {
    "memory-mcp": {
      "command": "D:\\git\\ai\\memory-mcp\\.venv\\Scripts\\memory-mcp.exe",
      "cwd": "D:\\git\\ai\\memory-mcp"
    }
  }
}
```

Portable Python module form:

```json
{
  "mcpServers": {
    "memory-mcp": {
      "command": "D:\\git\\ai\\memory-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "memory_mcp.main"],
      "cwd": "D:\\git\\ai\\memory-mcp"
    }
  }
}
```

Keep `.env` in the repo root. The MCP process loads database settings from
there, while `.env` remains ignored by Git.

By default, MCP access is read-only for normal-sensitivity memory. Enable
additional capabilities only for trusted local clients:

```text
MEMORY_MCP_ENABLE_MUTATION_TOOLS=true
MEMORY_MCP_ENABLE_SENSITIVE_TOOLS=true
```

`MEMORY_MCP_ENABLE_MUTATION_TOOLS` enables `add_memory`, `archive_memory`,
`supersede_memory`, and `run_pruning_pass`. `MEMORY_MCP_ENABLE_SENSITIVE_TOOLS`
enables `include_sensitive=true` reads and echoed sensitive/private write
content or evidence.

## Client Configuration Locations

Exact UI paths change by client. The important part is to register one local
stdio MCP server named `memory-mcp`.

| Client | Where to configure |
| --- | --- |
| Cursor | Cursor settings or project MCP configuration, depending on your Cursor version. Use the stdio JSON shape above. |
| GitHub Copilot in VS Code | VS Code MCP server settings, commonly workspace `.vscode/mcp.json` or user settings. |
| Codex | Codex MCP configuration for the current profile or project. Keep project instructions in `AGENTS.md`. |
| Claude Code | `claude mcp add` or Claude Code settings. Keep project instructions in `CLAUDE.md`; add hooks only when you need deterministic enforcement. |

## Basic Usage

Search active normal-sensitivity memories:

```json
{
  "query": "memory-mcp retrieval architecture",
  "project": "memory-mcp",
  "include_global": true,
  "limit": 8
}
```

Generate a compact project context packet:

```json
{
  "request": "What should I remember while changing retrieval in memory-mcp?",
  "workspace": "ai",
  "project": "memory-mcp",
  "component": "retrieval",
  "include_global": true,
  "max_memories": 8,
  "max_tokens": 1200
}
```

Store a durable project fact:

```json
{
  "memory_type": "project_fact",
  "summary": "Retrieval uses PostgreSQL full-text ranking.",
  "content": "memory-mcp retrieval combines structured filters, PostgreSQL full-text search, confidence, recency, and bounded result counts.",
  "memory_scope": "component",
  "workspace": "ai",
  "project": "memory-mcp",
  "component": "retrieval",
  "applies_to": {
    "scope": "development"
  },
  "tags": ["retrieval", "postgres"]
}
```

This write example requires `MEMORY_MCP_ENABLE_MUTATION_TOOLS=true`. Scoped
project, workspace, and component writes default to `scope="development"` when
no explicit `applies_to.scope` is provided.

## Branch-Aware Usage

Use `scope_path` for nested project, repo, module, branch, feature, and session
context. Retrieval checks the direct scope first, then parent prefixes when
`include_inherited` is true.

```json
{
  "request": "Current attack-buffering architecture context",
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
```

Use `overrides_memory_ids` when a lower scope replaces inherited knowledge for
that scope without marking the parent memory globally superseded:

```json
{
  "memory_type": "architecture_decision",
  "summary": "combat-refactor uses event-driven attack input.",
  "content": "combat-refactor replaces direct PlayerAttack input polling with InputReader events.",
  "scope_path": [
    "global",
    "project:MetroidvaniaGame",
    "repo:unity-client",
    "app:gameplay",
    "module:combat",
    "branch:combat-refactor"
  ],
  "scope_type": "branch",
  "overrides_memory_ids": ["00000000-0000-0000-0000-000000000000"],
  "valid_from": "2026-04-24T00:00:00+00:00",
  "tags": ["architecture", "branch-note"]
}
```

## Recommended Agent Instructions

No custom client skill or hook is required for the server to work. The server is
most useful when each agent is instructed to retrieve narrow context before
substantial work and refresh durable project memory after meaningful changes.

Recommended files in consuming repositories:

| Client | Recommended file | Purpose |
| --- | --- | --- |
| Cursor | `.cursor/rules/memory-mcp.mdc` | Tell Cursor agents when to call `get_context_packet`, `search_memory`, and `add_memory`. |
| GitHub Copilot | `.github/copilot-instructions.md` | Document the memory workflow for Copilot Chat/agent sessions. |
| Codex | `AGENTS.md` | Project instruction file; use the workflow in this repository's current AGENTS instructions. |
| Claude Code | `CLAUDE.md` | Persistent Claude Code project guidance. |

Minimal instruction text:

```markdown
Use the `memory-mcp` MCP server for durable project memory.

Before substantial implementation, review, or planning:
- Prefer `get_context_packet` with the narrowest project/component/scope_path.
- Use `include_global=true` when global preferences may apply.
- Keep `include_sensitive=false` unless the user explicitly asks.
- Do not enable mutation or sensitive MCP capabilities unless the current local
  client is trusted.

After meaningful project work:
- Store only durable, non-sensitive project facts.
- Prefer compact summaries over transcripts or logs.
- Use component or scope_path context for branch/module-specific facts.
- Use overrides_memory_ids for branch-local replacements.
```

## Optional Claude Code Hooks

Hooks are optional. Add them only if you want deterministic logging or guardrails
around memory writes.

Example: log all `memory-mcp` tool calls.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__memory-mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": "echo Memory MCP tool call >> %USERPROFILE%\\memory-mcp-hooks.log"
          }
        ]
      }
    ]
  }
}
```

Example: review writes before they run. Implement the script locally to reject
secrets, connection strings, or sensitive personal data.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__memory-mcp__add_memory",
        "hooks": [
          {
            "type": "command",
            "command": "python D:\\git\\ai\\memory-mcp\\scripts\\validate_memory_write.py"
          }
        ]
      }
    ]
  }
}
```

The validation script is not included yet. Add it only if you need enforced
write policy beyond agent instructions.

## What Not To Do

- Do not expose this MCP server to untrusted remote clients.
- Do not store secrets, tokens, API keys, connection strings, or customer data.
- Do not use broad unscoped searches when a project, component, or `scope_path`
  is known.
- Do not store raw transcripts when a compact fact, decision, or workflow
  location is enough.
- Do not globally supersede main-branch facts for branch-only changes; use
  `scope_path` plus `overrides_memory_ids`.

## Source Links For Version Checks

- Cursor download page: https://cursor.com/en-US/download
- VS Code Copilot MCP docs: https://code.visualstudio.com/docs/copilot/customization/mcp-servers
- GitHub Copilot marketplace: https://marketplace.visualstudio.com/items?itemName=GitHub.copilot
- Codex releases: https://github.com/openai/codex/releases
- Claude Code MCP docs: https://code.claude.com/docs/en/mcp
- Claude Code hooks docs: https://code.claude.com/docs/en/hooks
