# MMCP-016B — Install receipts and local update checks

**Priority:** P1
**Status:** Backlog
**Blocked by:** MMCP-016A
**Parent:** MMCP-016

## Goal

Record non-secret plugin render receipts and report local-only updates by
comparing an installed receipt with the currently available marketplace plugin.

## Scope Of Work

- Write `.memory-mcp/plugins/<plugin-name>.lock.json` after a successful render.
- Include plugin id, plugin version, manifest schema version, source marketplace
  path, rendered client target, selected server profile name when present, and
  render timestamp.
- Add `memory-mcp plugins check-updates --marketplace <path>`.
- Add `memory-mcp plugins check-updates <plugin-name> --install-root <dir>`.
- Compare local receipt version against the local marketplace plugin version.
- Report the render command needed to update when a newer local plugin is
  available.

## Out Of Scope

- Remote marketplace fetching.
- Automatic updates.
- Downloading plugin packages.
- Credential storage.
- Server profile creation.

## Acceptance Criteria

- `check-updates` reports no update when the receipt version matches the local
  marketplace plugin version.
- `check-updates` reports installed version, available version, source path, and
  render command when the local plugin version is newer.
- Receipts never contain secrets, tokens, API keys, refresh tokens, connection
  strings, or raw identity payloads.
- Missing receipts and missing marketplace plugins produce clear errors.

## Test Plan

- Receipt writer emits the expected non-secret JSON shape.
- Update checker reports no update for matching versions.
- Update checker reports an available update for newer marketplace versions.
- Update checker handles missing receipt and missing plugin cases.
