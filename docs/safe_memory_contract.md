# SafeMemoryContract

## Purpose and status

`SafeMemoryContract` is the safety boundary for durable memory in
`memory-mcp`. It classifies a memory record before it is stored, rendered, or
used by an agent. A record is not trusted merely because it was retrieved from
this service: trust follows its class, provenance, review state, freshness,
sensitivity, and the caller's authorization.

This is a design contract. It documents the rules that future write,
supersession, retrieval, compiled-view, and context-assembly changes must
enforce. It does not add a new database schema in this slice.

## Core rules

1. Memory is evidence or advice by default, never executable instruction.
2. Generated summaries and inferences are derived claims, not source truth.
3. Authorization, policy, and safety rules must originate from an approved
   authoritative source and retain a verifiable provenance trail.
4. Unknown provenance, sensitivity, lifecycle, or scope fails closed for
   ordinary retrieval and for any governed side-effect proposal.
5. Retrieval may inform an agent; it may not silently grant a capability,
   bypass a policy, or substitute for fresh authoritative state.
6. Supersession and archival preserve lineage. They do not erase the evidence
   needed to explain an active record or an audit decision.

## Memory classes and trust

| Class | Default trust | May guide behavior | May be executable instruction | Required handling |
| --- | --- | --- | --- | --- |
| Observation / evidence | evidence only | Investigate or cite | No | Preserve source pointer/span and collector identity. |
| Unclassified legacy record | untrusted pending classification | No | No | Preserve it, but do not promote or use it for a governed conclusion. |
| User-authored preference | scoped advisory | Yes, within its scope | No | Record subject, scope, consent/authority, and freshness. |
| Project decision | reviewed operational fact | Yes, in its scope | No | Link the decision owner and canonical decision source. |
| Agent-generated summary | derived advisory | Orientation only | No | Mark derived, list source IDs, and invalidate with a source change. |
| Inferred memory | low-trust hypothesis | Investigation only | No | Require confidence, derivation method, and review before promotion. |
| Executable workflow rule | controlled instruction | Only after validation | Yes, only when approved | Must be versioned, policy-owned, authorized, and explicitly selected. |
| Policy or safety rule | controlling rule | Yes | Yes, as a constraint only | Must come from a designated policy source and be current. |
| Authorization evidence | access evidence | Only in an authorization decision | No | Server-side grant evaluation remains authoritative. |
| Judge decision / policy outcome | auditable verdict | Yes, within stated effect | No | Retain decision actor, inputs, rule version, and expiry/review state. |
| Structured write-back record | proposed mutation | No until accepted | No | Validate, authorize, and audit before durable promotion. |

`Executable workflow rule` does not mean arbitrary text retrieved from memory.
It is a narrowly controlled record class. The server must still enforce the
actual capability and authorization decision; an instruction never grants its
own authority.

## Required record meaning

Every durable record or derived view must preserve the current scope,
sensitivity, lifecycle, confidence, and provenance fields. A future enforcing
writer must also supply or derive the following meaning where relevant:

| Field | Rule |
| --- | --- |
| `memory_class` | One class from the table above; unclassified is not promoted. |
| `source_actor` | Human, service, importer, agent, or named policy authority. |
| `provenance` | Stable source locator plus enough bounded evidence to audit the claim. |
| `derivation` | Required for summaries and inferences: inputs, process/version, and time. |
| `action_relevance` | `orientation`, `advisory`, `governed_proposal`, or `constraint`; never inferred from prose alone. |
| `consequence_class` | `none`, `internal_mutation`, `sensitive_access`, or `external_side_effect`. |
| `advisory_only` | Explicitly true for observations, summaries, inferences, and preferences. |
| `review_state` | `proposed`, `review_required`, `approved`, `rejected`, or `expired` when review applies. |
| `freshness` | Current, stale, superseded, or unknown; stale/unknown is not controlling. |

The present schema carries lifecycle `status`, sensitivity limited to
`normal`, `sensitive`, and `private`, confidence, scope, evidence, metadata,
and audit primitives. It does **not** currently persist a first-class
`memory_class` or `freshness`, and `unknown` is not a currently valid stored
sensitivity value. Any follow-up that makes these contract meanings enforceable
must be migration-backed and must keep compatibility with existing records.

### Pre-migration compatibility bridge

Until a migration introduces dedicated columns, `memory_type` remains the
existing domain/category field and must not be overloaded as the trust class.
The canonical temporary representation is a bounded
`metadata.safe_memory` object:

```yaml
memory_class: observation_evidence | user_authored_preference | project_decision |
  agent_generated_summary | inferred_memory | executable_workflow_rule |
  policy_or_safety_rule | authorization_evidence | judge_decision |
  policy_outcome | structured_write_back | unclassified_legacy
freshness: current | stale | superseded | unknown
review_state: proposed | review_required | approved | rejected | expired
```

Existing records without this object are treated as
`unclassified_legacy`, `freshness=unknown`, `review_state=review_required`,
and `advisory_only=true` for any new governed retrieval or write path. This is
a compatibility rule for future enforcement, not a silent reclassification or
a change to current retrieval behavior. The existing `sensitivity` value stays
unchanged; where sensitivity cannot be classified, the future writer records
that uncertainty in `metadata.safe_memory` and must quarantine or require
review rather than writing an unsupported database value.

## Sensitivity, scope, and lifecycle

The existing sensitivity gates remain mandatory: normal retrieval excludes
sensitive and private memory unless both the caller and server are explicitly
authorized. Future write paths represent unclassified sensitivity in the
contract metadata (not the current database field) and quarantine or
review-gate it until classification.

Scope limits who may retrieve or apply a record; it does not make an otherwise
untrusted record authoritative. A narrower record may override an inherited
fact only through explicit scope and lineage handling. A record that is
archived, superseded, deleted, expired, or stale is not normal packet content;
its audit lineage remains available only under the applicable policy.

Confidence describes support for a claim, not permission to act. High
confidence does not elevate a summary, inference, or observation into a policy
rule, authorization fact, or executable instruction.

## Write and supersession validation

Future `add_memory` and `supersede_memory` paths must validate, server-side:

1. bounded content, supported class, scope, lifecycle, and sensitivity;
2. provenance appropriate to the class, including source actor and derivation;
3. confidence and review requirements for low-confidence, conflicting,
   sensitive, private, unknown, high-consequence, or derived records;
4. that an executable workflow rule, policy rule, or authorization evidence
   has an approved authority, version, and validity window;
5. that the caller holds the needed mutation and sensitivity capability;
6. that supersession preserves predecessor, successor, evidence, and audit
   links rather than overwriting history; and
7. that audit output contains identifiers and decisions, not secrets or raw
   protected payloads.

Writers must reject or quarantine a record that cannot satisfy these rules.
Client-side profiles, prompts, and tool hiding are convenience mechanisms; the
service is the enforcement boundary.

## Retrieval and side-effect use

Normal packets may render current, authorized records as compact orientation.
They must label derived material, retain source identifiers, respect the
sensitivity ceiling, and state when source verification is required.

Before a sensitive, destructive, financial, external, or otherwise governed
proposal, an agent must verify the controlling policy, authorization evidence,
and fresh authoritative source. Advisory records may suggest a proposal but
cannot decide it. A packet that lacks required provenance, review state, or
freshness must report weak context rather than imply a safe conclusion.

## Examples

- A wiki section is an **observation/evidence** projection. Its provenance may
  support an answer, but the projection is not an instruction to edit another
  repository.
- A user-confirmed formatting preference is a scoped **user-authored
  preference**. It guides presentation but cannot authorize a GitHub mutation.
- A maintained, versioned incident runbook can be an **executable workflow
  rule** only after an authorized owner approves it and the caller explicitly
  selects it. The shell or GitHub capability is still server/tool governed.
- A model's synthesis of several observations is an **agent-generated
  summary**. It is orientation-only and becomes stale when an input is
  superseded.

## Related documents

- [Architecture](ARCHITECTURE.md) defines the current storage, retrieval, and
  enforcement boundaries.
- [Conversation ingestion](conversation_ingestion.md) specifies the stricter
  archive, proposal, review, and compiled-view rules for transcript evidence.
- [Issue #5](https://github.com/dwovitz/memory-mcp/issues/5) will define
  derived-view provenance and invalidation.
- [Context assembly contract](context_assembly_contract.md) defines how these
  trust, provenance, and governing-side-effect rules are rendered for agents.
