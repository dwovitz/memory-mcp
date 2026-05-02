# Memory Benchmark Prompt: Outline Feature Work

Case id: `outline_feature_api_collection_invites`
Variant: `memory`

Use the real Outline repository at `D:\git\ai\outline` as the source checkout.
Create a fresh isolated worktree branched from `origin/main`:

```powershell
$source = "D:\git\ai\outline"
$workspace = "D:\git\ai\outline-benchmarks\outline_feature_api_collection_invites\memory"
$branch = "benchmark/outline_feature_api_collection_invites-memory"
git -C $source fetch origin main
git -C $source worktree add -B $branch $workspace origin/main
Set-Location $workspace
```

If that worktree path already exists or is dirty, stop and choose a new empty
workspace path with a short timestamp suffix. Do not overwrite prior benchmark
results.

Task: Implement collection-level invite expiration settings in the Outline API.

Before reading source broadly, retrieve a `memory-mcp` context packet with:

```text
workspace="ai"
project="outline"
component="api"
request="Implement collection-level invite expiration settings in the Outline API."
include_global=true
include_inherited=true
include_sensitive=false
max_tokens=1200
```

Use the packet's `context_quality`, `suggested_next_action`,
`source_read_policy`, `source_read_budget_tokens`, `source_read_limits`, and
`verification_focus` to decide how much source to inspect before editing. Track
how many source files and snippets you read before the first edit. If you exceed
the recommended budget, record the specific exception you used. Then make the
smallest coherent implementation and focused tests you can justify from the
codebase.

If fast search is unavailable, use path-only fallback before snippet reads. Do
not use fallback commands whose primary output is matching source lines from
many files. If fallback search starts printing source lines, stop immediately,
discard that output as search context, rerun path-only search, and record
`fallback_search_mode: content_dump`; accidental source-output fallback means the source-read budget was not obeyed.

path-only fallback search does not authorize large source-output reads from
selected files. After path-only discovery, read only bounded snippets from selected files
and keep each snippet within `source_read_limits.max_lines_per_snippet`
when that value is nonzero. If a command returns oversized source output before
the first edit, discard it as context, rerun a bounded read, and record
`max_snippet_lines_obeyed: no`; oversized snippets before first edit mean `source_read_budget_obeyed: no`
unless you recorded an explicit budget exception
before exceeding the limit.

Bounded snippets still count toward `source_read_limits.max_snippets`.
Staying under `source_read_limits.max_lines_per_snippet` is not enough if
`source_read_limits.max_snippets` is exceeded. Before the first edit, inspect only the top few directly implicated files/snippets.
Stop at `source_read_limits.max_snippets` before the first edit.
If more snippets are needed before the first edit, name the missing fact, likely file/symbol, and why the current bounded snippets are insufficient before reading more.
Exceeding `source_read_limits.max_snippets` before first edit means `source_read_budget_obeyed: no` unless an explicit exception was recorded before exceeding it.

Avoid whole-file formatting or line-ending rewrites unrelated to the fix. Prefer
formatter checks first. If formatting is required, keep it limited to
intentionally touched files and call out any broad formatter churn in notes.

Fallback search reporting:

- `fallback_search_mode: none` means no degraded fallback search was needed.
- `fallback_search_mode: path_only` means fallback discovery only printed paths,
  such as `git grep -l`, `grep -R -l`, targeted `git ls-files` filtering, or
  `Select-String -List` over known candidate files.
- `fallback_search_mode: content_dump` means a fallback search printed matching
  source lines from one or more files. If this happens, stop that command
  immediately, discard the output as discovery context, rerun path-only search,
  and record whether the broad output was stopped.

Formatting churn reporting:

- `none` means no unrelated formatting or line-ending churn.
- `limited` means formatter changes are confined to intentionally touched hunks/files and small enough to review inline.
- `broad` means whole-file formatting, line-ending rewrites, or very large same-file diffs unrelated to the fix, even if only one or two files changed.

End with this exact fenced block:

```text
BENCHMARK_RESULT
case_id: outline_feature_api_collection_invites
project: outline
variant: memory
worktree:
branch:
benchmark_invalid: no
memory_used: yes
memory_context_quality:
memory_source_read_policy:
memory_source_read_budget_tokens:
source_read_budget_obeyed: yes/no
source_files_read_count:
source_snippets_read_count:
source_budget_exception:
max_snippet_lines_obeyed: yes/no
fallback_search_mode: none/path_only/content_dump
fallback_search_commands:
broad_search_output_stopped: yes/no/n/a
files_inspected_before_edit:
files_changed:
formatting_churn: none/limited/broad
tests_run:
outcome:
notes:
```
