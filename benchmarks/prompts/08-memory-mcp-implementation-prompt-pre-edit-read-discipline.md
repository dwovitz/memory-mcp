# Product Improvement Prompt: Implementation Pre-Edit Read Discipline

Run this from:

```text
D:\git\ai\memory-mcp
```

Implement the next benchmark-guidance fix for `memory-mcp`.

Goal:
Tighten `implementation_required` context-packet guidance so agents stop
pre-edit source inspection earlier after path-only discovery. The previous
strict fallback work improved degraded-search behavior, but memory benchmark
agents still exceeded file/snippet budgets before the first edit.

Recent benchmark evidence:

- Post-reset rerun directory:
  `D:\git\ai\memory-mcp\benchmarks\results\runs\20260430-144130`
- `outline_feature_update_collection_default_permissions` memory rerun was
  valid and improved fallback behavior:
  `fallback_search_mode: path_only`, `broad_search_output_stopped: n/a`.
  It still failed the source-read budget:
  `source_read_budget_obeyed: no`, `source_files_read_count: 18`,
  `source_snippets_read_count: 35`.
  The reported exception was that initial direct source snippets exceeded
  max-lines, max-files, and max-snippets before first edit.
- `outline_feature_update_comment_resolution_audit` memory rerun was valid and
  also improved fallback behavior:
  `fallback_search_mode: path_only`, `broad_search_output_stopped: n/a`.
  It still failed the source-read budget:
  `source_read_budget_obeyed: no`, `source_files_read_count: 9`,
  `source_snippets_read_count: 20`.
  The reported exception was that bounded source reads exceeded the 60-line
  snippet limit and then exceeded max files/snippets while locating event hook
  and test context.

What this means:

- Do not rework the degraded-search fallback fix. It helped: agents switched
  from `content_dump` to `path_only`.
- The remaining failure is pre-edit read discipline for
  `source_read_policy: implementation_required`.
- Agents need an explicit checkpoint after path-only discovery and before
  reading more source. If the likely edit surface is still unclear after the
  allowed pre-edit snippets, they should either edit the most likely boundary,
  ask for/record a budget exception, or mark the benchmark budget as not
  obeyed before reading more.

Product changes to implement:

1. Strengthen `implementation_required` source-read guidance.

   Keep existing `source_read_policy` names and existing budget fields
   backward-compatible. Preserve component fallback behavior and
   sensitive/private memory gating.

   Update rendered guidance and structured diagnostics so agents see:

   - Path-only discovery comes first.
   - After path-only discovery, select a small candidate set before opening
     source files.
   - For `implementation_required`, pre-edit reading is a phased workflow:
     1. enumerate likely paths,
     2. choose the top candidate files,
     3. read only bounded snippets from those candidates,
     4. stop at the budget checkpoint before reading more,
     5. make the first edit or explicitly record a budget exception.
   - Reading additional files/snippets before the first edit requires naming
     the missing fact and counts as a budget failure in benchmark reporting
     unless the benchmark explicitly allows it.
   - Do not read tests, model, route, presenter, policy, migration, and client
     files all up front by default. Pick the most likely entry point and one or
     two directly adjacent boundaries first; expand only after the first edit
     or after recording the exception.
   - Snippet size limits are hard pre-edit limits. Do not read oversized chunks
     and later describe them as bounded.

   Add structured diagnostics if useful, for example:

   - `pre_edit_path_discovery_required: true`
   - `pre_edit_candidate_selection_required: true`
   - `pre_edit_budget_checkpoint_required: true`
   - `extra_pre_edit_reads_require_exception: true`
   - `extra_pre_edit_reads_count_as_budget_failure: true`
   - `pre_edit_sequence: [...]`
   - `pre_edit_stop_rule: "..."`
   - `pre_edit_expansion_rule: "..."`

   Existing diagnostics such as `source_read_limits`,
   `source_read_budget_tokens`, `path_only_search_first`, and strict fallback
   fields should remain present.

2. Tighten memory benchmark implementation prompts.

   Update complex memory implementation benchmark prompts where relevant:

   - `benchmarks/prompts/05b-memory-outline-feature-update-collection-default-permissions.md`
   - `benchmarks/prompts/06b-memory-outline-feature-update-comment-resolution-audit.md`

   Make the pre-edit budget accounting explicit:

   - Agents must record the files/snippets read before the first edit.
   - Agents must distinguish path-only discovery from source snippet reads.
   - Agents must record whether they hit the pre-edit budget checkpoint before
     reading more.
   - Agents must record whether they named a missing fact before exceeding the
     budget.
   - Agents must mark `source_read_budget_obeyed: no` if they exceed
     file/snippet/line limits before the first edit, even if fallback search was
     path-only.

   Add or preserve result fields:

   ```text
   pre_edit_budget_checkpoint_hit: yes/no
   extra_pre_edit_reads_exception_recorded: yes/no/n/a
   pre_edit_source_files_read_count:
   pre_edit_source_snippets_read_count:
   max_snippet_lines_obeyed: yes/no
   ```

   Keep existing result fields:

   ```text
   source_read_budget_obeyed: yes/no
   source_files_read_count:
   source_snippets_read_count:
   source_budget_exception:
   fallback_search_mode: none/path_only/content_dump
   fallback_search_commands:
   broad_search_output_stopped: yes/no/n/a
   formatting_churn: none/limited/broad
   ```

3. Update tests.

   Add or update tests proving:

   - `implementation_required` rendered guidance includes a pre-edit
     checkpoint and says extra pre-edit reads require an exception.
   - Structured diagnostics include the pre-edit discipline fields.
   - Existing `source_read_policy` names remain unchanged.
   - Existing strict fallback diagnostics remain present.
   - Memory benchmark prompts include the new pre-edit accounting fields.
   - Memory benchmark prompts still require `source_read_budget_obeyed: no`
     when pre-edit file/snippet/line limits are exceeded.

Likely files:

- `src/memory_mcp/services/context_synthesis.py`
- `tests/test_context_synthesis.py`
- `tests/test_benchmark_cases.py`
- `benchmarks/prompts/05b-memory-outline-feature-update-collection-default-permissions.md`
- `benchmarks/prompts/06b-memory-outline-feature-update-comment-resolution-audit.md`

Possibly:

- `src/memory_mcp/mcp_tools/server.py`
- `tests/test_mcp_tools.py`
- `benchmarks/prompts/README.md`

Constraints:

- Do not rewrite retrieval ranking.
- Do not loosen sensitive/private memory gating.
- Preserve component fallback behavior.
- Preserve existing `source_read_policy` names.
- Preserve the strict fallback-search fields added by the prior fix.
- Keep this focused and incremental.
- Avoid whole-file formatting or line-ending rewrites unrelated to the fix.

Run tests:

```powershell
pytest tests/test_context_synthesis.py tests/test_benchmark_cases.py tests/test_mcp_tools.py
pytest
```

If Docker is available after the fix, update the local instance:

```powershell
docker compose build memory-mcp
docker compose up -d postgres
docker compose up -d memory-mcp
docker compose ps
```

Then rerun the affected memory benchmark cases:

```powershell
$agentCommand = "codex exec --dangerously-bypass-approvals-and-sandbox"
.\.venv\Scripts\python.exe benchmarks\run_outline_benchmarks.py `
  --agent-command $agentCommand `
  --cases outline_feature_update_collection_default_permissions,outline_feature_update_comment_resolution_audit `
  --variants memory `
  --iterations 1 `
  --timeout-seconds 3600
```

End by reporting changed files, test results, Docker outcome, rerun directory,
whether the fallback mode stayed `path_only`, and whether pre-edit budget
compliance improved.
