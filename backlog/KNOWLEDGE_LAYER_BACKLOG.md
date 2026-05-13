# Knowledge Layer Backlog

This backlog captures architecture and implementation planning inspired by Nate's `RAG Agents / Knowledge Layer Architecture` article and adjacent agentic-RAG knowledge-layer patterns.

The article reinforces several existing `memory-mcp` directions:

- durable provenance-aware memory
- consolidation/dream passes
- compiled memory views
- scoped retrieval
- retrieval trust boundaries
- evidence-aware summaries
- bounded context packets

This backlog extends those ideas into explicit knowledge-layer governance so the system scales beyond "vector search plus summaries".

## Priority summary

| ID | Title | Priority | Recommended placement | Status | Notes |
|---|---|---:|---|---|---|
| MMCP-KL-001 | Define retrieval evidence envelope | P0 | Before broader autonomous retrieval consumers | Backlog | Normalize provenance/freshness/trust metadata across retrieval paths. |
| MMCP-KL-002 | Add freshness and decay semantics to memory records | P0 | Before compiled-view promotion becomes authoritative | Backlog | Distinguish durable truths from stale or weakly-supported observations. |
| MMCP-KL-003 | Define retrieval-grade tiers for memory consumers | P0 | Before `ai-os` action planning relies on memory retrieval | Backlog | Different consumers need different evidence quality requirements. |
| MMCP-KL-004 | Add contradiction and conflict-set indexing | P1 | Before large-scale consolidation/dream automation | Backlog | Preserve disagreement explicitly instead of flattening memory into summaries. |
| MMCP-KL-005 | Define progressive-disclosure context packets | P1 | Before large memory deployments | Backlog | Retrieval should emit bounded layered context, not giant dumps. |
| MMCP-KL-006 | Add retrieval observability and audit trails | P1 | Before autonomous write-back or self-improvement loops | Backlog | Track what evidence influenced generated outputs/actions. |

## Story detail

### MMCP-KL-001 — Define retrieval evidence envelope

**Behavior:** define a normalized retrieval evidence envelope returned by retrieval and compiled-context APIs.

**Intent:** every retrieved memory/context artifact should carry enough metadata to support freshness evaluation, provenance tracing, sensitivity enforcement, and safe downstream usage.

**Recommended fields:**

- memory identifier
- source memory identifiers
- retrieval timestamp
- original observation timestamp
- freshness/staleness classification
- confidence
- source actor
- memory class from SafeMemoryContract
- scope and tenant/workspace boundaries
- sensitivity class
- derived/generated status
- superseded/archived/conflicted status
- allowed downstream usage
- provenance chain references

**Acceptance criteria:**

- Add design documentation for the retrieval evidence envelope.
- Cross-link with `MMCP-004 SafeMemoryContract`.
- Define serialization behavior for MCP consumers.
- Define how compiled summaries preserve provenance links.
- Define how stale or conflicted evidence is surfaced instead of silently hidden.

### MMCP-KL-002 — Add freshness and decay semantics to memory records

**Behavior:** define how memories age, decay, become stale, or require reconfirmation.

**Intent:** not all memories are equally durable. User-authored durable preferences differ from inferred summaries or transient observations.

**Acceptance criteria:**

- Define freshness classes and decay policies.
- Define reconfirmation requirements for inferred or weak-confidence memories.
- Define how compiled views react when upstream memories become stale.
- Define retrieval ranking adjustments based on age plus confidence plus repetition.
- Define how stale memories remain auditable without polluting active context packets.

### MMCP-KL-003 — Define retrieval-grade tiers for memory consumers

**Behavior:** define retrieval quality tiers for different downstream consumers.

**Example tiers:**

- orientation-only context
- briefing-grade context
- planning-grade context
- judge-evidence-grade context
- action-authority-grade context

**Acceptance criteria:**

- Define minimum provenance/freshness/trust requirements per tier.
- Define which memory classes are allowed in each tier.
- Define when compiled summaries are sufficient versus when raw source records must be checked.
- Align with `ai-os` Action Governance and future Knowledge Layer contracts.

### MMCP-KL-004 — Add contradiction and conflict-set indexing

**Behavior:** add explicit contradiction tracking instead of attempting to flatten disagreements during consolidation.

**Intent:** long-term memory systems should preserve uncertainty and conflict instead of silently converging on the newest or loudest summary.

**Acceptance criteria:**

- Define contradiction-set representation.
- Define superseded versus unresolved-conflict behavior.
- Define retrieval behavior for conflicts.
- Define how compiled summaries surface unresolved disagreement.
- Define how Memory Dream consolidation interacts with contradiction sets.

### MMCP-KL-005 — Define progressive-disclosure context packets

**Behavior:** define layered context packets that progressively expand detail instead of returning large flat memory dumps.

**Recommended layers:**

- orientation summary
- active facts
- decisions and constraints
- supporting evidence
- detailed source records
- archived/stale/conflict references

**Acceptance criteria:**

- Define packet size budgets.
- Define deterministic ordering rules.
- Define escalation rules for requesting deeper detail.
- Define compatibility with Claude/Codex token-saving workflows.
- Align with thedotmack/claude-mem inspired progressive disclosure patterns already discussed for the project.

### MMCP-KL-006 — Add retrieval observability and audit trails

**Behavior:** define observability and audit requirements for retrieval-driven reasoning.

**Acceptance criteria:**

- Define what retrieval operations are logged.
- Define how generated summaries reference retrieval inputs.
- Define how downstream action proposals or judge decisions can trace evidence.
- Define privacy-sensitive logging boundaries.
- Define bounded retention for retrieval telemetry.

## Relationship to existing backlog

These stories extend and refine:

- MMCP-001 Memory Dream consolidation
- MMCP-004 SafeMemoryContract
- MMCP-005 durable compiled memory views

They should generally be treated as architecture gates before broad autonomous write-back, self-improvement, or action-authority behavior is enabled.
