# AI Indexing

## Purpose

AI index files give agents a stable map of the repo before they inspect source files or rely on GitHub search.

The index is a navigation layer, not a replacement for source inspection. Its job is to help agents decide where to start, which files are authoritative, which graph/context tools should be used first, which commands validate a scoped change, and which memory/safety contracts must not be broken.

Required files:

- `AGENTS.md` — shared agent source of truth and startup order.
- `AI_INDEX.md` — repo navigation and operating map.
- `AI_ARCHITECTURE.md` — architectural boundaries and runtime model.
- `.ai/index.json` — future machine-readable index maintained by automation.

Tool-specific files such as `CLAUDE.md`, `CODEX.md`, or command wrappers should stay thin and point back to the shared index and agent instructions instead of duplicating durable project policy.

## What The Index Is Not

Do not treat the AI index as:

- a complete semantic embedding store;
- a generated summary of every file;
- a substitute for reading the narrow source files required by the active issue;
- a place to paste long model-specific prompting advice;
- a stale snapshot that automation blindly trusts.

A stale index is worse than a small index. Prefer compact, reviewable maps that point to authoritative source files, graph/context tools, and validation commands.

## Required Agent Startup Order

Agents should load context in this order:

1. `AGENTS.md`
2. `AI_INDEX.md`
3. `AI_ARCHITECTURE.md`
4. Tool-specific instructions such as `CLAUDE.md` or `CODEX.md`
5. The active GitHub Issue/story
6. Graph/context tools
7. Relevant workflow, policy, or architecture docs named by the index
8. Narrow source files identified by the index, graph, and issue

Use broad search only when these files and graph/context tools do not identify a useful starting path.

## Layered Instructions

Keep durable service policy in shared files and keep context layered:

| Layer | Purpose |
|---|---|
| `AGENTS.md` | Tool-neutral operating rules, startup order, safety boundaries, and closeout expectations. |
| `AI_INDEX.md` | Repo map, major entrypoints, source-of-truth files, common task starting points, graph/context usage, and known non-editable/generated paths. |
| `AI_ARCHITECTURE.md` | MCP service architecture, storage/retrieval boundaries, scope model, context packet behavior, and durable contracts. |
| Tool-specific files | Thin adapters for Claude, Codex, OpenCode, or future harness-specific behavior. |
| Local generated regions | Automation-owned sections that can be refreshed without overwriting human-authored intent. |

Large repos may add local agent guidance under major subdirectories, but local files must not conflict with the root source of truth.

## Scoped Validation Map

Every maintained index should point agents to the smallest meaningful validation loop for common change types. Prefer a command map over generic "run all tests" instructions.

Examples:

- documentation-only change: no runtime validation unless commands/examples changed;
- MCP tool contract change: contract/unit tests plus sample tool-call behavior where practical;
- retrieval/context packet change: targeted retrieval tests plus source-read-policy behavior checks;
- storage/migration change: storage tests plus migration compatibility evidence;
- scope/sensitivity change: tests proving isolation and non-sensitive defaults;
- Docker/deployment change: explicit Docker/runtime probe, not just native command success.

If validation commands live elsewhere, `AI_INDEX.md` should link to that file instead of duplicating a long command list.

## Maintenance Rule

Update the AI index files in the same change when work modifies:

- MCP tool contracts;
- storage or retrieval architecture;
- context packet behavior;
- scope model or sensitivity semantics;
- deployment/Docker assumptions;
- entity graph behavior;
- major directories or entrypoints;
- agent workflow expectations;
- validation commands or closeout evidence expectations;
- generated-file boundaries or paths agents must not edit.

## Automation Policy

Automation should assist maintenance, not overwrite intent.

- `ai-index-check` should detect missing files, missing required sections, and architecture-sensitive changes without corresponding index updates.
- `ai-index-refresh` should update generated regions only.
- Stop-hook or closeout reflection may propose index updates while context is fresh.
- Human-authored intent, boundaries, and safety rules must not be blindly regenerated.
- Any generated update should be reviewable in a normal diff.

## Commands

Run these commands from the repository root:

```powershell
python scripts/ai_index_refresh.py
python scripts/ai_index_check.py --base origin/main
```

`ai_index_refresh.py` rewrites only the `repo-map` region bounded by
`AI-GENERATED:START` and `AI-GENERATED:END` in `AI_INDEX.md`, and rewrites the
automation-owned `.ai/index.json`. It never edits the surrounding purpose,
architecture, ownership, safety, or validation prose.

`ai_index_check.py` verifies required index files, the JSON shape, and that the
generated region equals the repository map the refresh tool would produce. It
also examines paths changed since `--base` (default: `origin/main`). Changes to
MCP, storage, retrieval, authorization, ingestion, hooks, migrations, Docker,
or package configuration require at least one maintained index file in the
same diff. Use `--changed path/to/file` for a deterministic local or test-only
check without consulting Git.

## Generated Regions

Future automation should only rewrite generated regions marked like this:

```md
<!-- AI-GENERATED:START repo-map -->
<!-- AI-GENERATED:END repo-map -->
```

Use generated regions for compact inventories, detected commands, or directory maps. Keep design intent, ownership boundaries, and safety policy outside generated regions.

## Completion Check

Before closing a story, answer:

1. Did this change alter how future agents should navigate the repo?
2. Did this change alter MCP behavior or contracts?
3. Did this change alter storage, retrieval, scope, or safety behavior?
4. Did this change add, remove, or rename a major component?
5. Did this change affect cross-agent usability?
6. Did this change affect validation commands or the smallest meaningful test loop?
7. Did this change affect generated files, hidden paths, or machine-readable index expectations?

If yes, update `AGENTS.md`, `AI_INDEX.md`, `AI_ARCHITECTURE.md`, and/or `.ai/index.json` as appropriate. If no, record why no index update was needed in the run summary or Next Step Packet.
