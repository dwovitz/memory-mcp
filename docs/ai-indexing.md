# AI Indexing

## Purpose

AI index files give agents a stable map of the repo before they inspect source files or rely on GitHub search.

Required files:

- `AGENTS.md` — shared agent source of truth.
- `AI_INDEX.md` — repo navigation and operating map.
- `AI_ARCHITECTURE.md` — architectural boundaries and runtime model.
- `.ai/index.json` — future machine-readable index maintained by automation.

## Required Agent Startup Order

Agents should load context in this order:

1. `AGENTS.md`
2. `AI_INDEX.md`
3. `AI_ARCHITECTURE.md`
4. Tool-specific instructions such as `CLAUDE.md` or `CODEX.md`
5. The active GitHub Issue/story
6. Graph/context tools
7. Narrow source files identified by the index, graph, and issue

## Maintenance Rule

Update the AI index files in the same change when work modifies:

- MCP tool contracts;
- storage or retrieval architecture;
- context packet behavior;
- scope model or sensitivity semantics;
- deployment/Docker assumptions;
- entity graph behavior;
- major directories or entrypoints;
- agent workflow expectations.

## Generated Regions

Future automation should only rewrite generated regions marked like this:

```md
<!-- AI-GENERATED:START repo-map -->
<!-- AI-GENERATED:END repo-map -->
```

Human-authored intent, boundaries, and safety rules should not be blindly regenerated.

## Completion Check

Before closing a story, answer:

1. Did this change alter how future agents should navigate the repo?
2. Did this change alter MCP behavior or contracts?
3. Did this change alter storage, retrieval, scope, or safety behavior?
4. Did this change add, remove, or rename a major component?
5. Did this change affect cross-agent usability?

If yes, update `AGENTS.md`, `AI_INDEX.md`, and/or `AI_ARCHITECTURE.md` as appropriate.
