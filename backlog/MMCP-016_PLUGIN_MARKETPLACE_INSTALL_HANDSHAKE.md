# MMCP-016 — Plugin marketplace install handshake and update checks

**Priority:** P1
**Status:** Backlog
**Blocked by:** MMCP-002

## Goal

Make local marketplace plugins safe to install and maintain by adding version
checks, first-run server binding, and authentication profile handoff for client
setup packs.

This story complements hosted/remote auth hardening. Hosted mode owns
server-side authorization. This story owns client-side plugin install behavior:
which server a rendered client connects to, how auth requirements are surfaced,
and how installed plugin packs check for local updates.

## Scope Of Work

- Extend plugin manifests with `schema_version`, package `version`,
  `min_memory_mcp_version`, `update_channel`, supported server connection modes,
  and supported client targets.
- Write non-secret install receipts under
  `.memory-mcp/plugins/<plugin-name>.lock.json` after rendering a plugin.
- Add local update checks that compare install receipts against the current
  local marketplace plugin version and report the render command needed to
  update.
- Add a first-run setup flow that asks which memory-mcp server profile to use:
  local Docker Compose, local HTTP hook endpoint, remote authenticated server,
  or manually supplied MCP stdio command.
- Store non-secret server profile metadata under
  `.memory-mcp/profiles/<profile-name>.json`.
- Require authentication metadata for remote or auth-enabled server profiles,
  but never store tokens, API keys, refresh tokens, or connection strings in
  rendered repository files.
- Render profile names or environment variable references into Codex, Claude
  Code, VS Code Copilot, and Cursor outputs.

## Acceptance Criteria

- `memory-mcp plugins check-updates` reports no update when the receipt matches
  the local plugin version.
- `memory-mcp plugins check-updates` reports the installed and available version
  when the local plugin version is newer than the receipt.
- First-run setup records a non-secret profile for local Docker and manual stdio
  server choices.
- First-run setup refuses a remote/auth-enabled server profile unless an auth
  profile or environment-backed credential reference is provided.
- Rendered outputs never contain secrets and include only profile names or
  environment variable references for credentials.

## Dependencies

- MMCP-002 for the CLI shape and auth profile command surface.
- Existing `src/memory_mcp/auth/` and the hosted/remote hardening roadmap for
  server-side authorization behavior.
