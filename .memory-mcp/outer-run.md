# Outer-Harness Execution Contract — memory-mcp

Defines how outer-harness runs (Claude Code, Codex CLI, or local workers)
execute issues against this repository. memory-mcp is a retrieval/projection
service backed by PostgreSQL + pgvector; it is not an unchecked runtime
assistant.

## What outer-harness means here

Outer-harness: the AI agent implements the issue directly — edits files,
runs validation, commits, and opens a PR — without delegating to a
self-hosted automation pipeline. All outer-harness runs in this repo are
`route:outer-harness` (see `.memory-mcp/issue-contract.md`).

## Preflight checklist

Run all preflight checks **before** beginning implementation. Abort and
report specifically if any check fails.

1. **Readiness gate** — confirm `status:ready` label is present.
2. **Score gate** — evaluate readiness score ≥ 0.7 per `.memory-mcp/issue-contract.md`.
3. **Required sections** — confirm Phase, Goal, Scope, Out of scope,
   Acceptance criteria, Dependency, and `## AI documentation impact` are
   all present and non-empty.
4. **Documentation impact** — read the `## AI documentation impact` section
   and record which files need updating (or record the rationale if none).
5. **Memory context** — call `get_context_packet(workspace="ai",
   project="memory-mcp", repo="memory-mcp")` and inspect `context_quality`,
   `warnings`, and `suggested_next_action` before reading source.
6. **Graph context** — call `detect_changes` + `get_review_context` (or
   `get_impact_radius` for the affected area) before editing files.
7. **Branch base** — fetch `origin/main` and cut the branch from it:
   `git fetch origin && git checkout -b mmcp-{n}-{slug} origin/main`.
   Never branch off the current HEAD or local `main`.

If preflight fails: stop, report the specific failing items, and do not
proceed to implementation.

## Execution phases

```
1.  Preflight (above)
        ↓
2.  Context narrowing
        memory-mcp context packet → AGENTS.md / CLAUDE.md → issue body
        → relevant docs → narrow source files identified by memory/graph
        → broad file search only when layers above do not resolve the path
        ↓
3.  Branch
        git fetch origin
        git checkout -b mmcp-{n}-{slug} origin/main
        ↓
4.  Implementation
        Edit files directly per the issue scope.
        Do not implement anything listed in "Out of scope."
        ↓
5.  Validation
        pytest tests/ -x -q
        (or: pytest <specific-module> when change is narrowly scoped)
        mypy src/ --ignore-missing-imports   # type check
        ↓
6.  Documentation impact resolution
        Apply any updates listed in the preflight step (4).
        If no-update-needed: record the rationale in the PR body.
        ↓
7.  Commit
        git add <specific files>
        git commit -m "MMCP-{n}: {title}"
        ↓
8.  PR
        gh pr create --title "MMCP-{n}: {title}" --body "..."
        Include: Closes #{n}, outer-run trace, AI documentation impact decision.
        Do NOT use --draft.
        ↓
9.  Closeout report
        State: issue number, branch, PR URL, validation result,
        AI documentation impact decision, and any open risks.
```

## Model and effort guidance

Use the smallest model that preserves quality. Escalate only when scope or
risk requires it.

| Work type | Claude model | Effort |
|---|---|---|
| File search, log scanning, read-only exploration | Haiku 4.5 | low |
| Documentation and contract updates | Sonnet 4.6 | med |
| Schema or migration changes | Sonnet 4.6 | high |
| Retrieval logic, context assembly, embedding pipeline | Sonnet 4.6 | high |
| Privacy / PII handling, data minimization | Opus 4.8 | high |
| Security review, auth, broad architecture | Opus 4.8 | high |
| Implementation + tests (standard) | Sonnet 4.6 | med–high |

| Work type | Codex model | Effort |
|---|---|---|
| File search, read-only exploration | gpt-5.4-mini | low |
| Documentation and contract updates | gpt-5.1-codex | med |
| Schema or migration changes | gpt-5.1-codex | high |
| Retrieval logic, privacy, security | gpt-5.5-codex | high |
| Implementation + tests (standard) | gpt-5.1-codex | med–high |
| Adversarial review | gpt-5.5-codex | high |

## Validation commands

```bash
# Full test suite
pytest tests/ -x -q

# Narrowly scoped (e.g., only memory retrieval tests)
pytest tests/test_retrieval.py -x -q

# Type check
mypy src/ --ignore-missing-imports

# Lint (if configured)
ruff check src/ tests/
```

Validation must pass before committing. If validation fails after
implementation, diagnose root cause — do not bypass with `# noqa`, `# type:
ignore`, or skipped tests unless the issue scope explicitly permits it and the
rationale is recorded in the PR body.

## Route guidance

### route:outer-harness

Default for all issues in this repository until an inner-harness path is
established. The AI agent implements directly.

Trigger for escalating within outer-harness (use stronger model/effort):
- Privacy or PII scope
- Security or authentication changes
- Schema migrations affecting stored data
- Changes to the context assembly contract
- Changes to readiness gates or execution contracts

### route:inner-harness

Not currently configured in this repository. If labeled `route:inner-harness`,
an agent should stop and request clarification.

## Commit convention

```
MMCP-{issue-number}: {short imperative title}
```

## PR body template

```markdown
## Summary
<1-3 bullets>

## Outer-run trace
- Mode: outer-harness direct implementation
- Orchestration agent: <claude|codex|manual>
- Validation: <passed|failed — details>
- AI documentation impact: <updates-required: [files] | no-update-needed: rationale>

## Test plan
- [ ] pytest tests/ passes
- [ ] mypy src/ passes
- [ ] Acceptance criteria verified

Closes #{issue-number}
```

## Closeout requirements

Before marking done:
- All acceptance criteria verified (check each one explicitly).
- Validation passed (record the command and result).
- AI documentation impact resolved (files updated or rationale recorded).
- PR is open and not draft.
- No `status:ready` label is removed by this run — label cleanup is human's
  responsibility post-merge.
