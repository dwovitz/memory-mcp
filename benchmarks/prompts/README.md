# Outline Benchmark Prompt Pairs

Paste one prompt into a fresh agent. Each prompt creates or uses an isolated
Outline worktree under:

```text
D:\git\ai\outline-benchmarks
```

Every benchmark case has two prompts:

- `baseline`: use only the Outline repository and normal source inspection.
- `memory`: retrieve `memory-mcp` context for `workspace="ai"` and
  `project="outline"` before source inspection.

Both variants start from `origin/main` in their own worktree and finish with a
`BENCHMARK_RESULT` block so results can be compared directly.

| Case | Baseline prompt | Memory prompt |
| --- | --- | --- |
| `outline_feature_api_collection_invites` | `01a-baseline-outline-feature-api-collection-invites.md` | `01b-memory-outline-feature-api-collection-invites.md` |
| `outline_bug_fix_search_authorization` | `02a-baseline-outline-bugfix-search-private-title-leak.md` | `02b-memory-outline-bugfix-search-private-title-leak.md` |
| `outline_validation_plan_wrong_component_fallback` | `03a-baseline-outline-validation-plan-api-endpoint.md` | `03b-memory-outline-validation-plan-api-endpoint.md` |

## Product Improvement Prompt

After running the benchmark pairs, use
`04-memory-mcp-improvement-plan-from-results.md` to ask a fresh agent to plan
product changes for `memory-mcp` based on the saved comparison artifacts.

Additional product improvement prompts:

- `12-memory-mcp-implementation-prompt-token-budgeted-benchmark-runs.md`:
  add benchmark run modes, token preflight, budget enforcement, and compact
  artifacts so routine benchmark runs do not consume unbounded tokens.
- `13-codex-token-budgeted-outline-benchmark-loop.md`: run the updated
  token-budgeted benchmark loop, collate compact artifacts, review evidence,
  and create a focused `fix-prompt.md` when results justify another iteration.
