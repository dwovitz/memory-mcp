# MMCP-006 — Define context assembly contract for agent knowledge packets

## Status

Backlog

## Priority

P0

## Source

Nate's Newsletter May 13 signal: production RAG / agent knowledge is not just vector search. The useful layer is context assembly: current records, permissions, controlling policies, source trails, prior decisions, structured sections, memory, access control, provenance, and write-back.

## Goal

Define a `memory-mcp` context assembly contract so agents receive governed, provenance-backed knowledge packets instead of raw memory-search blobs.

## Problem

`memory-mcp` already provides `get_context_packet`, scoped retrieval, source-read guidance, sensitivity controls, provenance/evidence, and bounded token budgets. The missing contract is a named boundary that says what a context packet must include before an agent relies on it for planning, coding, review, or side-effect proposal generation.

Without that contract, agents may treat retrieved text as complete context even when permissions, stale sources, policy constraints, provenance, or write-back requirements are missing.

## Proposed contract dimensions

A context assembly response should explicitly model:

- request purpose and classified task type
- caller principal / auth context when available
- requested workspace, project, component, topic, branch, or `scope_path`
- matched memory scopes and inheritance behavior
- source memory IDs and provenance references
- sensitivity and redaction mode
- access-control / grant assumptions
- relevant policy or safety constraints
- prior decisions and whether they are active, superseded, or stale
- compiled view references when used
- source-read policy and token budget
- context quality diagnostics
- missing-context warnings
- write-back expectations after the agent completes work

## Acceptance criteria

- Add a design doc under `docs/` defining the context assembly contract.
- Define how this contract relates to existing `get_context_packet` output.
- Define required versus optional fields for coding, review, planning, and governed-action-preparation requests.
- Define how provenance, permissions, sensitivity, policy constraints, compiled views, and source-read budgets appear in the assembled context.
- Define when weak context must be marked explicitly instead of silently returning a plausible packet.
- Define write-back guidance so agents know what durable facts, decisions, or corrections should be proposed after work.
- Identify whether current context packet schema is sufficient or whether a small schema/API change is needed.
- Cross-link with `MMCP-004` SafeMemoryContract and `MMCP-005` durable compiled memory views.

## Non-goals

- Do not replace structured retrieval or context packets.
- Do not require vector search before embedding decisions are accepted.
- Do not expose sensitive/private memory by default.
- Do not make compiled summaries canonical truth.
- Do not implement broad UI/reporting in this story.

## Notes

This is distinct from `MMCP-004`: SafeMemoryContract governs what memory records mean and how trustworthy they are. `MMCP-006` governs how selected memory, provenance, policy, permissions, and write-back guidance are assembled into an agent-facing knowledge packet.