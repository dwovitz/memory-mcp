# MMCP-016D — Auth handoff for remote/auth-enabled profiles

**Priority:** P1
**Status:** Backlog
**Blocked by:** MMCP-016C
**Parent:** MMCP-016

## Goal

Make remote or auth-enabled plugin profiles safe by requiring auth profile names
or environment-backed credential references while never storing credential
values in repo files, render outputs, receipts, or profiles.

## Scope Of Work

- Extend server profile validation so remote/auth-enabled profiles require an
  auth profile name or environment variable reference.
- Render auth profile names or environment variable names into supported client
  outputs where needed.
- Integrate with existing `src/memory_mcp/auth/` concepts and hosted/remote
  hardening direction without implementing a full auth provider.
- Document which credential storage locations are delegated to the host client,
  OS credential store, environment variables, or a future explicit auth-profile
  mechanism.

## Out Of Scope

- Storing access tokens, refresh tokens, API keys, client secrets, or connection
  strings.
- Implementing a full auth-profile secret manager.
- Server-side hosted authorization changes.
- Remote marketplace fetching.

## Acceptance Criteria

- Setup refuses a remote/auth-enabled profile unless an auth profile name or
  environment-backed credential reference is provided.
- Rendered outputs never contain credential values.
- Rendered outputs use auth profile names or environment variable names only.
- Documentation clearly separates client auth handoff from server-side
  authorization.

## Test Plan

- Remote profile without auth metadata fails validation.
- Remote profile with auth profile name passes validation.
- Remote profile with environment variable reference passes validation.
- Secret-looking auth metadata values are rejected.
- Rendered outputs include only auth references, not credential values.
