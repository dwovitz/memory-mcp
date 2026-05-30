# Canonical Backlog

GitHub Issues are now the canonical backlog and execution source of truth for `memory-mcp`.

This file is retained only as a migration index for legacy backlog references. Do not add new implementation stories here. Do not treat this file as controlling implementation state when it conflicts with GitHub Issues.

## Current source-of-truth policy

- New implementation work must be created as a GitHub Issue.
- Selected stories, bugs, follow-ups, security work, and execution handoffs belong in GitHub Issues.
- Design notes may still live under `docs/` or `.ai/design/`, but the controlling work item should be linked from a GitHub Issue.
- Specs may still live under `.ai/specs/`, but the GitHub Issue remains the implementation tracker.
- This file should only be updated to preserve migration mappings or remove stale references.

## Current direction guardrails

Future issues and implementations should preserve these architectural decisions:

- The Docker-backed `memory-mcp` service owns persistence, schema, retrieval, graph operations, auth/policy, and audit.
- MCP plugin launchers/profiles are thin client-facing surfaces. They connect to the separately running service and do not embed or duplicate the backend/database.
- GitHub Issues are the canonical work tracker.
- Structured memory records remain source of truth.
- Context packets and compiled views are derived/projection artifacts, not canonical truth.
- Provenance/evidence must be preserved for durable memory and derived views.
- Sensitive/private memory requires explicit gates and server-side authorization.
- Coding-agent profiles must stay compact and token-bounded.
- `ai-os` may use richer graph-connected context, but still through sensitivity/provenance controls.
- Graph retrieval must be bounded and must not become a graph dump.
- Service-side enforcement is required; plugin-side tool hiding is not a security boundary.

## Migrated backlog items

| Legacy ID | Title | Canonical GitHub Issue | Status |
|---|---|---:|---|
| MMCP-001 | Implement scheduled memory consolidation worker | #22 | Open |
| MMCP-002 | Build CLI for memory-MCP | #6 | Reopened |
| MMCP-003 | Track 1: Auto-capture + distillation | #3 | Reopened |
| MMCP-004 | Define SafeMemoryContract for trusted durable memory | #4 | Reopened |
| MMCP-005 | Add durable compiled memory views with source provenance | #5 | Reopened |

## Related canonical GitHub Issues added after migration

| Issue | Title | Purpose |
|---:|---|---|
| #7 | MMCP-006: Define context assembly contract for agent knowledge packets | Governed, provenance-backed context assembly contract |
| #8 | MMCP-007: Harden MCP-facing contracts for protocol-clean reusable memory tools | MCP contract hardening |
| #13 | Add MCP/tool trust boundaries and composition-safety checks | Tool/memory trust and composition safety |
| #16 | Add conversation transcript ingestion and provenance-backed memory extraction | Transcript evidence and extracted durable memory |
| #17 | Add graph-first entity and relationship retrieval | Bounded graph retrieval and connected memory recall |
| #18 | Add MCP usage profiles and instructions for different agent workflows | Role-specific MCP usage/profile instructions |
| #19 | Add profile-specific MCP plugin launchers for Docker-backed memory service | Thin plugin launchers connecting to Docker service |
| #20 | Add client setup and compatibility validation for Claude Code, Codex, VS Code Copilot, and Cursor | Client setup and compatibility validation |
| #21 | Secure plugin-to-service connection for Docker-backed memory server | Auth/security for plugin-to-service boundary |

## Legacy note

The previous version of this file stated that the repo-local file backlog was the source of truth and that GitHub Issues should only be created for selected implementation work. That policy is superseded.

Use GitHub Issues for backlog planning, execution, audit, and handoff state going forward.