# Product Improvement Prompt: Strict Fallback Search And Baseline Isolation

Run this from:

```text
D:\git\ai\memory-mcp
```

Implement the next benchmark-guidance fix for `memory-mcp`.

Goal:
Tighten source-read guidance so degraded search cannot silently become broad
source-output reading, and make baseline benchmark prompts invalid if they use
memory despite the baseline rules.

Recent benchmark evidence:

- `01b` memory feature implementation still failed the source-read budget:
  `source_files_read_count: 156`, `source_snippets_read_count: 1409`. The
  failure mode was `rg` being denied, then `git grep -n` accidentally producing
  broad matching-line output while attempting path-only fallback.
- `02b` memory bug fix also failed the source-read budget:
  `source_files_read_count: 6`, `source_snippets_read_count: 14`. The failure
  mode was `rg` being denied, then fallback grep producing broad match output.
- `02a` baseline rerun was contaminated: it reported `variant: baseline` but
  `memory_used: yes` because repo AGENTS memory workflow overrode the baseline
  prompt. Treat that run as invalid for baseline comparison.
- `01a` baseline and `01b` memory reported `formatting_churn: none`; the field
  is useful. `02b` likely underreported churn as `limited` even though a large
  same-file diff looked broad, so churn definitions should be clearer.

Product changes to implement:

1. Strengthen degraded-search fallback guidance in context packets.

   Keep existing `source_read_policy` names and existing budget fields
   backward-compatible. Preserve component fallback behavior and sensitive
   memory gating.

   Update rendered guidance and structured diagnostics so agents see:

   - Fast search unavailable means path-only fallback first.
   - Allowed fallback examples are path-output commands only, such as:
     `git grep -l <term>`, `grep -R -l <term> <candidate-dirs>`,
     `git ls-files` with targeted filtering, and `Select-String -List` over
     known candidate files.
   - Disallowed fallback examples include `git grep -n`, `git grep` without
     `-l`, recursive `grep` without `-l`, `Select-String` without `-List` when
     used as discovery, `Get-Content` over many files, and any command whose
     primary output is matching source lines from many files.
   - If a fallback search starts printing source lines, stop immediately,
     discard that output as a search source, rerun path-only search, and count
     the incident as a budget failure if the benchmark asks.
   - After path-only search, read only bounded snippets from selected files.

   Add structured diagnostics if useful, for example:

   - `path_only_search_first: true`
   - `broad_fallback_search_disallowed: true`
   - `fallback_search_examples: [...]`
   - `fallback_search_disallowed_examples: [...]`
   - `stop_on_source_output_fallback: true`
   - `fallback_source_output_counts_as_budget_failure: true`

2. Tighten benchmark implementation prompts.

   Update implementation benchmark prompts for both baseline and memory
   variants where relevant:

   - Baseline rules override repo/project AGENTS memory workflow for benchmark
     purposes. The baseline agent must not call `memory-mcp`.
   - If local instructions would require memory during a baseline run, stop and
     report the run as invalid instead of continuing with memory.
   - Add or preserve a result field:
     `benchmark_invalid: yes/no`
   - Add fallback-search result fields:
     `fallback_search_mode: none/path_only/content_dump`
     `fallback_search_commands:`
     `broad_search_output_stopped: yes/no/n/a`
   - For memory variants, preserve existing source-read fields and make clear
     that accidental source-output fallback still means the budget was not
     obeyed.
   - Keep `formatting_churn: none/limited/broad`, and define it more clearly:
     `none` means no unrelated formatting or line-ending churn; `limited` means
     formatter changes are confined to intentionally touched hunks/files and
     small enough to review inline; `broad` means whole-file formatting,
     line-ending rewrites, or very large same-file diffs unrelated to the fix,
     even if only one or two files changed.

3. Update tests.

   Add or update tests proving:

   - Rendered context packet guidance says path-only fallback comes before
     snippet reads when fast search is unavailable.
   - Rendered guidance explicitly disallows broad source-output fallback and
     names disallowed command forms like `git grep -n`.
   - Structured diagnostics include the strict fallback fields.
   - Implementation benchmark prompts include baseline invalid-run handling,
     fallback search metrics, and formatting churn definitions.
   - Existing source_read_policy names remain unchanged.

Likely files:

- `src/memory_mcp/services/context_synthesis.py`
- `tests/test_context_synthesis.py`
- `tests/test_benchmark_cases.py`
- `benchmarks/prompts/01a-baseline-outline-feature-api-collection-invites.md`
- `benchmarks/prompts/01b-memory-outline-feature-api-collection-invites.md`
- `benchmarks/prompts/02a-baseline-outline-bugfix-search-private-title-leak.md`
- `benchmarks/prompts/02b-memory-outline-bugfix-search-private-title-leak.md`

Possibly:

- `src/memory_mcp/mcp_tools/server.py`
- `tests/test_mcp_tools.py`
- `benchmarks/prompts/README.md`

Constraints:

- Do not rewrite retrieval ranking.
- Do not loosen sensitive/private memory gating.
- Preserve component fallback behavior.
- Preserve existing `source_read_policy` names.
- Keep this focused and incremental.
- Avoid whole-file formatting or line-ending rewrites unrelated to the fix.

Run tests:

```powershell
pytest tests/test_context_synthesis.py tests/test_benchmark_cases.py tests/test_mcp_tools.py
pytest
```

End by reporting changed files, test results, and whether project memory was
refreshed.
