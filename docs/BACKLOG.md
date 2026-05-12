# memory-mcp Backlog

This file tracks focused GitHub-backed backlog items for `memory-mcp`. GitHub issues are the actionable backlog source; this file is a compact repo-local index for active architectural direction.

## Source-of-truth policy

- GitHub issues are the actionable backlog records.
- This file should only summarize accepted or selected backlog direction.
- Prefer updating existing issues over creating duplicate architecture epics.
- Design work should land under `docs/` before implementation stories are split.

## Current selected / recommended stories

| Issue | Title | Priority | Status | Notes |
|---|---|---:|---|---|
| #4 | Define SafeMemoryContract for trusted durable memory | P0 | Backlog | Formalizes memory classes, trust levels, provenance, sensitivity, lifecycle, confidence, and executable-instruction rules. |
| #5 | Add durable compiled memory views with source provenance | P1 | Backlog | Defines wiki-style derived summaries backed by source memory IDs; depends conceptually on #4. |

## Immediate sequencing

1. Complete #4 first so memory classes and trust semantics are explicit.
2. Use #4 to define validation requirements for future `add_memory` and `supersede_memory` write paths.
3. Complete #5 after #4 so compiled views inherit the same source/provenance/trust rules.
4. Split implementation slices only after the design docs are accepted.

## Current rationale

`memory-mcp` already has structured memory, scoped retrieval, sensitivity controls, lifecycle states, provenance/evidence, context packets, pruning, auth, and audit logging. The remaining gap is making the safety contract explicit enough that future agents cannot treat arbitrary retrieved text or generated summaries as trusted executable instruction.
