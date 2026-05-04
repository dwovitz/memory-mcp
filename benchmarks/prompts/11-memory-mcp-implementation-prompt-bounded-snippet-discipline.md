# Product Improvement Prompt: Bounded Snippet Discipline

Run this from:

```text
D:\git\ai\memory-mcp
```

Implement the next benchmark-guidance fix for `memory-mcp`.

Goal:
Prevent memory benchmark agents from satisfying path-only fallback search rules
while still violating the source-read budget through oversized snippet reads.
The fix should make it explicit that `Select-String -List`, `git grep -l`, and
similar commands are discovery-only, and that any subsequent source inspection
must use small, bounded line windows.

Recent benchmark evidence:

- The resumed Outline benchmark loop produced after-evidence results in:

```text
benchmarks/results/runs/20260501-130208
```

- The original collated analysis, updated with resumed evidence, is:

```text
benchmarks/results/runs/20260501-085612/collated-analysis.md
```

- `outline_feature_update_collection_default_permissions` memory rerun obeyed
  the budget:
  - `source_read_budget_obeyed: yes`
  - `source_files_read_count: 15`
  - `source_snippets_read_count: 25`
  - `max_snippet_lines_obeyed: yes`

- `outline_feature_update_comment_resolution_audit` memory rerun failed the
  budget even though fallback search was reported as path-only:
  - `source_read_budget_obeyed: no`
  - `source_files_read_count: 5`
  - `source_snippets_read_count: 8`
  - `max_snippet_lines_obeyed: no`
  - `source_budget_exception: Oversized Select-String snippets from comments.test.ts and server/models/Comment.ts exceeded the 60-line per-snippet limit before first edit; no missing fact was named before exceeding.`

- The failure mode was not broad search-output fallback. It was broad
  post-discovery snippet reading: after path-only discovery, the agent used
  oversized `Select-String` output from selected files before first edit.

Product changes to implement:

1. Strengthen bounded-snippet guidance in context packets.

   Keep existing `source_read_policy` names and existing budget fields
   backward-compatible. Preserve component fallback behavior and sensitive
   memory gating.

   Update rendered guidance and structured diagnostics so agents see:

   - Path-only commands are discovery-only. They identify candidate files, not
     source context to consume.
   - `Select-String -List` is allowed only when used to list matching files.
   - `Select-String` output with matching source lines is source reading, not
     discovery.
   - After discovery, read only bounded snippets from selected files.
   - A bounded snippet should stay within the packet's advertised
     `max_lines_per_snippet` when that value is nonzero.
   - If a command returns more source lines than the snippet limit, stop using
     that output, discard it as context, rerun a bounded read, and count the
     incident as a source-read budget failure if the benchmark asks.
   - Before exceeding the snippet limit, the agent must name the missing fact,
     the likely file or symbol, and why that fact cannot be validated with a
     bounded snippet.

   Add structured diagnostics if useful, for example:

   - `path_only_discovery_only: true`
   - `select_string_list_only_for_discovery: true`
   - `bounded_snippets_after_discovery: true`
   - `oversized_snippet_counts_as_budget_failure: true`
   - `discard_oversized_snippet_output: true`

2. Tighten implementation benchmark prompts.

   Update implementation benchmark prompts for memory variants where relevant.
   Include the complex feature-update prompts if they do not already state this
   clearly:

   - `benchmarks/prompts/05b-memory-outline-feature-update-collection-default-permissions.md`
   - `benchmarks/prompts/06b-memory-outline-feature-update-comment-resolution-audit.md`

   Also update earlier memory implementation prompts if the shared prompt
   contract is tested across all implementation cases:

   - `benchmarks/prompts/01b-memory-outline-feature-api-collection-invites.md`
   - `benchmarks/prompts/02b-memory-outline-bugfix-search-private-title-leak.md`

   Prompt requirements:

   - Preserve current source-read result fields.
   - Preserve fallback search fields:
     - `fallback_search_mode: none/path_only/content_dump`
     - `fallback_search_commands:`
     - `broad_search_output_stopped: yes/no/n/a`
   - Add or clarify that path-only fallback search does not authorize large
     source-output reads from selected files.
   - Require bounded snippet reads after discovery.
   - Require `max_snippet_lines_obeyed: yes/no` when the prompt already tracks
     source-read budget details.
   - State that oversized snippets before first edit mean
     `source_read_budget_obeyed: no` unless an explicit budget exception was
     recorded before exceeding the limit.
   - Keep `formatting_churn: none/limited/broad` unchanged.

3. Update tests.

   Add or update focused tests proving:

   - Rendered context packet guidance distinguishes path-only discovery from
     bounded source snippet reading.
   - Rendered context packet guidance explicitly says `Select-String -List` is
     allowed for discovery but source-line `Select-String` output is a snippet
     read.
   - Rendered context packet guidance says oversized snippet output must be
     discarded and counted as a budget failure when benchmark tracking asks.
   - Structured diagnostics include bounded-snippet fields.
   - Memory benchmark prompts include bounded-snippet guidance and the
     `max_snippet_lines_obeyed` reporting requirement where applicable.
   - Existing `source_read_policy` names remain unchanged.

Likely files:

- `src/memory_mcp/services/context_synthesis.py`
- `tests/test_context_synthesis.py`
- `tests/test_benchmark_cases.py`
- `benchmarks/prompts/01b-memory-outline-feature-api-collection-invites.md`
- `benchmarks/prompts/02b-memory-outline-bugfix-search-private-title-leak.md`
- `benchmarks/prompts/05b-memory-outline-feature-update-collection-default-permissions.md`
- `benchmarks/prompts/06b-memory-outline-feature-update-comment-resolution-audit.md`

Possibly:

- `benchmarks/prompts/README.md`
- `tests/test_mcp_tools.py`

Constraints:

- Do not rewrite retrieval ranking.
- Do not loosen sensitive/private memory gating.
- Preserve component fallback behavior.
- Preserve existing `source_read_policy` names.
- Keep the change focused on source-read and prompt guidance.
- Avoid broad formatting churn or line-ending rewrites.
- Do not treat local Outline PostgreSQL authentication failures as product
  failures in `memory-mcp`.

Follow test-first discipline:

1. Add or update focused tests that fail on the missing bounded-snippet
   guidance.
2. Run those tests and confirm they fail for the expected reason.
3. Implement the minimal prompt/context guidance change.
4. Rerun the focused tests.
5. Rerun:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_context_synthesis.py tests\test_benchmark_cases.py tests\test_mcp_tools.py -q
```

6. Rerun full tests:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

If Docker is available after the fix, update the local instance:

```powershell
docker compose build memory-mcp
docker compose up -d postgres
docker compose up -d memory-mcp
docker compose ps
```

Then rerun the affected benchmark case first:

```powershell
$agentCommand = "codex exec --dangerously-bypass-approvals-and-sandbox"
.\.venv\Scripts\python.exe benchmarks\run_outline_benchmarks.py `
  --agent-command $agentCommand `
  --cases outline_feature_update_comment_resolution_audit `
  --variants memory `
  --iterations 1 `
  --timeout-seconds 3600 `
  --update-docker
```

If that memory-only rerun obeys the budget, run the paired comparison:

```powershell
$agentCommand = "codex exec --dangerously-bypass-approvals-and-sandbox"
.\.venv\Scripts\python.exe benchmarks\run_outline_benchmarks.py `
  --agent-command $agentCommand `
  --cases outline_feature_update_comment_resolution_audit `
  --variants baseline,memory `
  --iterations 1 `
  --timeout-seconds 3600 `
  --update-docker
```

Append the new rerun directory or directories to:

```text
benchmarks/results/runs/20260501-085612/collated-analysis.md
```

Project memory refresh:

- Use the `project-memory-refresh` skill after meaningful source or prompt
  changes.
- Store only durable project facts, not raw benchmark logs or transient
  debugging details.

End with this exact fenced block:

```text
BOUNDED_SNIPPET_RESULT
changed_files:
tests_added_or_updated:
focused_tests:
full_tests:
docker_updated: yes/no
affected_case_rerun:
paired_rerun:
source_read_budget_after:
collated_analysis_updated:
project_memory_refreshed:
remaining_followups:
```
