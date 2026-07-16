# Durable Compiled Memory Views

## Purpose and boundary

A compiled memory view is a durable, bounded projection of structured memory
for a defined orientation purpose. It improves repeatable human and agent
orientation without making summary prose a source of truth. The
[SafeMemoryContract](safe_memory_contract.md) applies to every input and view:
a view is derived, advisory by default, and never executable instruction.

This design distinguishes a compiled view from a request-time context packet:

| Artifact | Lifetime | Purpose | Authority |
| --- | --- | --- | --- |
| Context packet | Request/task scoped | Answer the present request under a token budget | Orientation only; verify as diagnostics require. |
| Compiled view | Durable but invalidatable | Reusable summary of a named scope or topic | Orientation only unless current source records are verified. |
| Source memory/evidence | Lifecycle-aware durable record | Support a claim or decision | Determined by its SafeMemoryContract class and provenance. |
| Authoritative external record | Source-system state | Resolve current issue, PR, policy, or grant state | Verify at the canonical system. |

The current schema already offers a useful implementation base: lifecycle-aware
`context_packets`, `context_packet_memories` foreign-key provenance, metadata,
scope, sensitivity, confidence, supersession, and expiry. The current
request-time synthesis service does not itself establish a compiled-view
registry, dependency index, or refresh worker. This story defines those future
semantics; it does not add a migration or runtime API. A small migration-backed
view registry and dependency metadata are required before compiled views can be
implemented safely; the existing packet tables are a provenance pattern, not a
complete durable-view implementation.

## Supported view types

| View type | Bounded contents | Intended reader |
| --- | --- | --- |
| Project summary | mission, active architecture, durable constraints | coding/planning agent or maintainer |
| Component summary | component boundary, conventions, known risks | scoped implementation/review agent |
| User preference summary | approved, scoped preferences only | authorized assistant |
| Active decisions summary | current reviewed decisions and their owners | planning/review agent |
| Workflow/rules summary | references to selected current rules, not copied authority | authorized operator/agent |
| Authorization/evidence summary | pointers, status, and freshness only | authorization-aware service path |
| Stale/conflict report | invalidated inputs, conflicts, refresh reason | maintainer or consolidation workflow |
| Memory health report | coverage, aging, duplication, and review gaps | operator |

Each type declares a scope, intended task class, sensitivity ceiling, source
verification policy, token/result budget, and refresh policy. A view must not
silently widen scope or sensitivity compared with any source.

## Provenance and view record

A compiled view must have a stable view ID and one dependency record per source
memory. The existing `context_packet_memories` relation is the preferred
foreign-key-backed pattern; follow-up persistence must preserve an equivalent
relationship rather than flattening source text into an opaque blob. Its
current cascading source deletion is not sufficient for durable views: the new
relation must either prevent physical source deletion while a view depends on
it or retain a redaction-safe, immutable dependency/audit snapshot.

Required metadata for a future durable view:

```yaml
view_id: stable identifier
view_type: project_summary | component_summary | ...
scope: workspace/project/repo/component/topic/scope_path
source_memory_ids: bounded ordered identifiers
dependencies:
  - memory_id: source identifier
    source_revision: lifecycle/version observation at generation
    provenance_or_evidence_ref: bounded source locator or immutable evidence reference
    trust_and_review_state: SafeMemoryContract class and review observation
    authority_or_access_ref: grant/policy reference when relevant
    observed_at: RFC 3339 dependency observation time
generation: generator identity, version, and timestamp
sensitivity_ceiling: normal | sensitive | private
freshness: current | stale | invalidated | unknown
verification_policy: orientation_only | verify_sources | canonical_source_required
safe_memory: class/derivation/review metadata required by SafeMemoryContract
supersedes_view_id: optional lineage pointer
```

Authorization or policy material is rendered as a source reference and current
verification requirement, never as an unsourced permission claim. A view must
not contain source content that a caller is not authorized to retrieve.

## Invalidation and refresh

A view becomes stale immediately when a source memory is superseded, archived,
deleted, redacted, reclassified, denied by a changed grant, or leaves the
view's scope or sensitivity ceiling. It also becomes stale when a dependency
loses provenance, a source review expires, or the view's generator/version no
longer satisfies its policy.

Invalidation is monotonic and auditable:

1. Record the source, event, timestamp, and affected view IDs.
2. Mark the view stale or invalidated without deleting its provenance links.
3. Exclude it from normal current-view selection; retain it for authorized
   audit and explanation.
4. Recompute only from current, authorized sources, producing a successor with
   explicit lineage.

Cache-version changes alone are not proof that a durable view is current. A
future refresh worker may optimize using them, but it must still check the
stored source dependency set and the governing lifecycle/access state.

## Retrieval and verification rules

Agents may use a current view directly for low-consequence orientation when:

- the task and scope match the view declaration;
- the caller is authorized for its sensitivity ceiling;
- provenance, freshness, and review diagnostics are complete; and
- the view says `orientation_only` or the task does not require a controlling
  conclusion.

Agents must verify source records when a conclusion is sensitive, destructive,
financial, authorization-relevant, externally side-effecting, contested, or
based on stale/unknown diagnostics. They must always verify a canonical
external source for live GitHub, policy, grant, or other source-system state.
A stale view can explain historical orientation but cannot support such a
conclusion.

Context packets may cite a compiled view as one bounded input, but must render
its view ID, freshness, verification policy, and source-read guidance. They
must not treat a view as a shortcut around SafeMemoryContract controls.

## Future implementation slices

1. Add a migration-backed compiled-view registry and dependency relation if
   the existing context-packet structures cannot provide durable indexing.
2. Add a bounded generator and deterministic source-dependency capture.
3. Add lifecycle, scope, sensitivity, grant, and provenance-triggered
   invalidation with audit records.
4. Add retrieval selection, explicit freshness diagnostics, and source
   verification policy to context assembly.
5. Test that source changes invalidate views, private sources do not leak, and
   stale views cannot support governed conclusions.

## Related documents

- [SafeMemoryContract](safe_memory_contract.md) defines the source trust and
  derived-artifact rules.
- [Retrieval and projection](retrieval.md) documents bounded, provenance-backed
  retrieval.
- [Conversation ingestion](conversation_ingestion.md) defines stricter
  evidence, review, and invalidation requirements for transcript-derived views.
- [Issue #7](https://github.com/dwovitz/memory-mcp/issues/7) will define how
  context assembly renders views and verification diagnostics.
