# MMCP-016C — First-run non-secret server profiles

**Priority:** P1
**Status:** Backlog
**Blocked by:** MMCP-016A
**Parent:** MMCP-016

## Goal

Add first-run profile selection so rendered plugin outputs can target a named
memory-mcp server profile without embedding secrets or mutating live client
configuration.

## Scope Of Work

- Add `.memory-mcp/profiles/<profile-name>.json` profile persistence.
- Support profile kinds:
  - local Docker Compose server
  - local already-running HTTP endpoint
  - remote authenticated server
  - manually supplied MCP stdio command
- Store non-secret metadata only: profile name, server kind, display name, MCP
  command shape, base URL where applicable, workspace default, repo default, and
  client target defaults.
- Add `memory-mcp plugins setup <plugin-name> --client <client>` interactive
  flow that creates or selects a profile and then delegates to render.
- Add non-interactive flags for profile name, server kind, base URL, workspace,
  repo, and manual stdio command shape.

## Out Of Scope

- Credential storage.
- Remote/auth-enabled credential validation beyond requiring a placeholder
  auth reference in `MMCP-016D`.
- Automatic mutation of live client config.
- Remote marketplace behavior.

## Acceptance Criteria

- Setup records a non-secret profile for local Docker.
- Setup records a non-secret profile for manual stdio.
- Rendered outputs can reference a selected profile name.
- Profile files reject secrets and credential-looking values.
- Non-interactive setup can run without prompts when required flags are
  supplied.

## Test Plan

- Profile model validates supported server kinds.
- Profile writer emits non-secret JSON.
- Setup creates local Docker and manual stdio profiles.
- Setup delegates to render with the selected profile.
- Secret-like profile values are rejected.
