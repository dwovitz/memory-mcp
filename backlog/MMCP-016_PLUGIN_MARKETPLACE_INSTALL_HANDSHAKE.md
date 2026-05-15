# MMCP-016 — Plugin marketplace umbrella

**Priority:** P1
**Status:** Split
**Design:** `docs/superpowers/specs/2026-05-15-plugin-marketplace-model-design.md`

## Goal

Turn the existing client setup templates into a local plugin marketplace model
without moving memory retrieval, storage, auth, or hook execution into a runtime
plugin system.

The marketplace owns plugin discovery, package metadata, deterministic client
rendering, install receipts, update checks, first-run server profile selection,
and safe auth handoff. The MCP server continues to own memory tools,
persistence, authorization, and hook behavior.

## Story Split

| ID | Title | Priority | Status | Blocked by |
|---|---|---:|---|---|
| MMCP-016A | Plugin package discovery and deterministic renderer | P1 | Ready | — |
| MMCP-016B | Install receipts and local update checks | P1 | Backlog | MMCP-016A |
| MMCP-016C | First-run non-secret server profiles | P1 | Backlog | MMCP-016A |
| MMCP-016D | Auth handoff for remote/auth-enabled profiles | P1 | Backlog | MMCP-016C |

## Sequencing

Implement `MMCP-016A` first. It creates an installable `memory-mcp-core` package
and render-only command surface without solving updates, setup profiles, or
remote auth.

After rendering exists, add receipts/update checks in `MMCP-016B`, then
non-secret first-run server profiles in `MMCP-016C`, then remote/auth-enabled
profile validation in `MMCP-016D`.

## Shared Constraints

- Do not execute arbitrary plugin install code in the first marketplace model.
- Do not dynamically load Python plugin code into the MCP server.
- Do not mutate live Codex, Claude Code, VS Code, Cursor, or user-level config
  files in the first marketplace stories.
- Do not store secrets, tokens, API keys, refresh tokens, connection strings, or
  raw identity payloads in plugin manifests, render outputs, receipts, or
  profile files.
- Keep `client-setups/` available as compatibility templates while plugin
  rendering becomes the preferred setup path.

## Implementation Notes

- Add focused `memory-mcp plugins ...` subcommands while preserving current
  `memory-mcp` behavior as the MCP server launcher when no plugin subcommand is
  supplied.
- A future broader CLI from `MMCP-002` can absorb these subcommands without
  changing plugin manifests or package layout.
- The first implementation story should use test-first development and keep
  hook behavior unchanged.
