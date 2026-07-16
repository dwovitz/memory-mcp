# Context Assembly Contract

## Purpose and boundary

The context assembly contract defines what an agent receives before it plans,
reviews, edits, or prepares a governed side-effect proposal. It turns bounded
retrieval into a structured, provenance-aware orientation packet; it does not
turn memory search into an authorization decision, a source of executable
instructions, or a substitute for canonical live state.

This contract extends the [SafeMemoryContract](safe_memory_contract.md) and
[durable compiled memory views](compiled_memory_views.md). The current
`get_context_packet` already returns rendered content, request classification,
quality diagnostics, warnings, source-read policy/budget, and cache-version
behavior. This design defines the complete packet shape future API work must
make explicit without broadening sensitivity or source-read access.

## Assembly inputs and required envelope

Every request is assembled under the caller's existing server-side
authorization. A packet is a response to an authorized read, not proof that
the caller may mutate data or take an external action.

| Field | Required | Meaning |
| --- | --- | --- |
| Request purpose and task class | Yes | Coding, review, planning, governed-action preparation, or another bounded class. |
| Caller/access context | Yes when available | Principal/grant decision reference and redaction mode; never raw credentials. |
| Scope request | Yes | Workspace/project/repo/component/topic or ordered `scope_path`; inheritance request is explicit. |
| Sensitivity request | Yes | Requested ceiling and whether sensitive evidence was authorized. |
| Retrieval budget | Yes | Result, token, traversal, and evidence limits. |
| Matched scope and sources | Yes | Actual scopes searched, source IDs/provenance references, and retrieval reasons. |
| Quality diagnostics | Yes | Quality, warnings, fallbacks, missing-context signals, and confidence limits. |
| Source-read contract | Yes | Suggested action, policy, token budget, and pre-edit limits. |
| Packet/version metadata | Yes | Contract version, generation time, cache/version token where supported. |
| Write-back guidance | Yes | Whether durable facts or corrections should be proposed after work. |

The effective scope and sensitivity in the response must be no broader than
what the caller requested and the server authorized. Missing caller identity,
grant context, source provenance, or sensitivity classification is a diagnostic
condition, not a reason to synthesize plausible authority.

## Task-class requirements

| Packet field | Coding | Review | Planning | Governed-action preparation |
| --- | --- | --- | --- | --- |
| Request/task classification | Required | Required | Required | Required |
| Scope and inheritance trace | Required | Required | Required | Required |
| Relevant memory/source references | Required | Required | Required | Required |
| Current decisions and constraints | Required | Required | Required | Required |
| Change/risk or review context | Required when available | Required | Optional | Required |
| Source-read contract | Required | Required | Required | Required |
| Compiled-view ID/freshness | Optional | Optional | Optional | Required if used |
| Policy/authorization reference | Optional | Required for security findings | Optional | Required |
| Write-back proposal guidance | Required | Required | Required | Required |
| Canonical-source verification | When implementation needs it | When a finding depends on it | When decisions are current | Always |

A packet may omit a field only by returning an explicit `not_available`,
`not_authorized`, or `not_applicable` state. It must not represent a missing
policy, source, or decision as a positive conclusion.

## Source and compiled-view handling

Each rendered retrieved claim—such as a fact, preference, or decision—needs a
bounded source record with a memory ID or canonical source pointer,
provenance/evidence reference, SafeMemoryContract class, lifecycle/freshness
observation, and retrieval reason. Derived summaries and compiled views
additionally include their generation/version, source dependency set, freshness,
sensitivity ceiling, and verification policy. System-generated diagnostics
(for example no-match, access denial, or budget exhaustion) instead carry a
diagnostic code/reason and packet-generator version; they must not fabricate a
memory source or evidence reference.

Compiled views can reduce orientation cost, but remain advisory. The packet
must surface their ID and source-read guidance, and agents must verify source
records for sensitive, contested, authorization-relevant, destructive,
financial, externally side-effecting, or stale conclusions. Live source-system
state—such as GitHub issue/PR status, grants, or policy versions—must be checked
at its canonical system.

## Quality and safe failure

The current quality values (`strong`, `usable`, `weak`, and `miss`) are
diagnostics, not trust levels. A strong result still cannot grant permission or
make a compiled summary canonical.

A packet must report `weak` or `miss`, along with a machine-readable reason,
when it has no scope match, only inherited broad facts, insufficient source
provenance, stale/invalidated dependencies, denied sensitivity access, an
expired review, or a budget that prevented required context. It may return
partial bounded orientation, but it must recommend `mark_weak_context` or
source verification instead of silently producing a confident-looking packet.

For a narrow component request, the existing one-time project-scope fallback
remains appropriate. If that fallback remains thin, the packet records the
attempt and does not authorize broad source dumping. The source-read contract
is authoritative for agent pre-edit limits.

## Write-back after work

Packets guide a proposal, not an automatic memory write. At completion, agents
should evaluate whether there is a durable, non-sensitive project fact,
decision, corrected stale record, or workflow constraint worth proposing.

A write-back proposal must include the changed scope, source or work evidence,
SafeMemoryContract class, confidence, sensitivity, freshness, and whether
review is required. It must never include secrets, raw protected payloads,
temporary logs, unverified speculation, or an authorization claim inferred from
the packet. Mutation, archive, supersession, and policy approval remain
server-side governed actions.

## Current contract and implementation follow-up

The current implementation already supports request classification, scope-aware
retrieval, normal-by-default sensitivity, bounded result/token budgets, quality
diagnostics, source-read policy and limits, and cache validation. It does not
yet expose a versioned, per-item structured envelope for all of the source,
principal/grant, policy, compiled-view, freshness, and write-back fields above.

A small API-contract follow-up is required to add that versioned envelope and
explicit unavailable/denied states to `get_context_packet`; it should reuse
existing source and scope data rather than add a parallel retrieval path. No
new memory schema is required for that envelope alone. Durable compiled-view
storage and dependency invalidation remain the migration-backed follow-up
identified in [compiled_memory_views.md](compiled_memory_views.md).

## Related documents

- [SafeMemoryContract](safe_memory_contract.md) defines trust classes and
  governing side-effect boundaries.
- [Durable compiled memory views](compiled_memory_views.md) defines source
  dependencies, invalidation, and orientation-only use.
- [Agent workflow](AGENT_WORKFLOW.md) explains the current source-read
  contract agents must follow.
- [Retrieval and projection](retrieval.md) defines bounded provenance-backed
  retrieval.
