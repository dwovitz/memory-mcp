# GitHub Issue Contract — memory-mcp

Aligned with the dark-factory issue contract. All execution-ready issues in
this repository must satisfy this contract before any harness (Claude Code,
Codex, or local worker) may begin implementation.

## Required labels

Every execution-ready issue must have **all four**:

- `status:ready` — hard requirement; missing = score 0.0, immediate abort
- `phase:{n}` — e.g. `phase:0`, `phase:1`
- At least one classification label (see below)
- Exactly one route label (see Route labels below)

## Classification labels

| Label | Meaning |
|---|---|
| `story:implementation` | Code change |
| `story:contract` | Schema or interface definition |
| `story:documentation` | Docs only |
| `story:migration` | Database or data migration |
| `story:retrieval` | Memory retrieval or search logic change |
| `story:privacy` | Privacy, data minimization, or PII handling |
| `type:epic` | Epic parent |
| `type:phase` | Phase definition |

## Route labels

| Label | Meaning |
|---|---|
| `route:outer-harness` | AI implements directly (Claude Code or Codex CLI) |
| `route:inner-harness` | Future: delegated to a self-hosted automation path |

Default to `route:outer-harness` unless an inner-harness path is explicitly
configured and tested in this repository.

## Required issue sections

```markdown
## Phase
Which phase this belongs to.

## Goal
What must be achieved.

## Scope
What is allowed.

## Out of scope
What must not be built.

## Acceptance criteria
How success is validated (checkbox list).

## Dependency
Required predecessor stories (by ID), or "None."

## AI documentation impact
Whether this story requires updates to AI-facing documentation.
Must use one of the two allowed forms:

  updates-required:
  - <concrete file or contract path>
  - <...>

  no-update-needed: <non-empty rationale explaining why no AI-facing docs,
  architecture context, workflow contracts, validation guidance, or generated
  index expectations are affected>

Stories missing this section, or with an empty or unrecognized form, must
be reported as not ready by every readiness path.
```

Optional sections:

```markdown
## Suggested route
Harness routing for this story.

- **Harness:** `outer` (default) | `inner` (only when inner-harness is available)
- **Claude:** Opus 4.8 (heavy/safety/security) | Sonnet 4.6 (standard) | Haiku 4.5 (trivial/read-only)
  — effort low | med | high
- **Codex:** gpt-5.5-codex (heavy) | gpt-5.1-codex (standard) | gpt-5.4-mini (read-only/search)
  — effort low | med | high

Apply the matching label: `route:outer-harness` or `route:inner-harness`.

## Definition of done
More precise than acceptance criteria when needed.
```

## Readiness scoring

An agent evaluating readiness scores 0.0–1.0:

| Check | Deduction |
|---|---|
| Missing `status:ready` | Hard fail (score = 0.0) |
| Title missing or < 5 chars | −0.3 |
| Body missing or < 20 chars | −0.4 |
| Missing phase label | −0.2 |
| Missing route label | −0.1 |
| No acceptance criteria | −0.1 |
| Missing `## AI documentation impact` section | Hard fail (also records −0.2 confidence deduction) |
| `## AI documentation impact` present but empty, unrecognized form, or no content | Hard fail (also records −0.1 confidence deduction) |
| Each ambiguity marker (`TBD`, `TODO`, `unclear`, etc.) | −0.1 (max −0.3) |

Score ≥ 0.7 required to proceed.

The `## AI documentation impact` section is a hard readiness requirement. A
story missing the section, or using an empty or unrecognized form, must be
reported as not ready regardless of score.

## Ambiguity markers

If any of these appear in the body, the score is reduced:

`tbd`, `todo`, `unclear`, `to be determined`, `not sure`, `maybe`,
`possibly`, `undecided`

Resolve them before labeling `status:ready`.

## Fail-closed rule

Agents must **fail closed** when any of the following are true:
- `status:ready` label is absent
- `## AI documentation impact` section is missing or malformed
- Readiness score < 0.7
- Required issue sections (Phase, Goal, Scope, Out of scope, Acceptance
  criteria, Dependency) are absent or contain only placeholder text

Failing closed means: stop, report the specific missing items, and do not
proceed with implementation. Do not attempt to infer intent or proceed under
ambiguity.
