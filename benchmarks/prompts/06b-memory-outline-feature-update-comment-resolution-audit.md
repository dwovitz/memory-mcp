# Memory Benchmark Prompt: Outline Complex Feature Update

Case id: `outline_feature_update_comment_resolution_audit`
Variant: `memory`
Complexity: `complex`

Use the real Outline repository at `D:\git\ai\outline` as the source checkout.
Create a fresh isolated worktree branched from `origin/main`:

```powershell
$source = "D:\git\ai\outline"
$workspace = "D:\git\ai\outline-benchmarks\outline_feature_update_comment_resolution_audit\memory"
$branch = "benchmark/outline_feature_update_comment_resolution_audit-memory"
git -C $source fetch origin main
git -C $source worktree add -B $branch $workspace origin/main
Set-Location $workspace
```

If that worktree path already exists or is dirty, stop and choose a new empty
workspace path with a short timestamp suffix. Do not overwrite prior benchmark
results.

Task: Add comment resolution audit metadata to the Outline API and event flow.

This is a complex feature update. Expect multi-boundary work across API request
validation, authorization policies, persistence, event payloads, and focused
tests.

Before reading source broadly, retrieve a `memory-mcp` context packet with:

```text
workspace="ai"
project="outline"
component="api"
request="Add comment resolution audit metadata to the Outline API and event flow."
include_global=true
include_inherited=true
include_sensitive=false
max_tokens=1200
```

Use the packet's `context_quality`, `suggested_next_action`,
`source_read_policy`, `source_read_budget_tokens`, `source_read_limits`, and
`verification_focus` to decide how much source to inspect before editing. Track
how many source files and snippets you read before the first edit. If fallback
search prints broad source-output lines instead of paths, stop that command,
rerun path-only search, and record the budget failure.

For pre-edit budget accounting, distinguish path-only discovery from source snippet reads.
You must record the files/snippets read before the first edit,
record whether you hit the pre-edit budget checkpoint before reading more, and
record whether you named a missing fact before exceeding the budget. Mark
`source_read_budget_obeyed: no` if you exceed file, snippet, or per-snippet line
limits before the first edit, even if fallback search was path-only.

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

Your objective is to obey the pre-edit limits, not only to report when they were
exceeded. At the pre-edit budget checkpoint, make the first edit at the most
likely boundary rather than continuing to read tests, model, route, presenter,
policy, migration, and client files all up front.
A recorded exception explains budget failure; it does not preserve compliance.

Avoid whole-file formatting or line-ending rewrites unrelated to the fix. Prefer
formatter checks first. If formatting is required, keep it limited to
intentionally touched files.

`formatting_churn: none` means no unrelated formatting or line-ending churn;
`limited` means formatter changes are confined to intentionally touched hunks or
files and small enough to review inline; `broad` means whole-file formatting,
line-ending rewrites, or very large same-file diffs unrelated to the fix.

End with this exact fenced block:

```text
BENCHMARK_RESULT
case_id: outline_feature_update_comment_resolution_audit
project: outline
variant: memory
worktree:
branch:
memory_used: yes
memory_context_quality:
memory_source_read_policy:
memory_source_read_budget_tokens:
benchmark_invalid: yes/no
source_read_budget_obeyed: yes/no
source_files_read_count:
source_snippets_read_count:
source_budget_exception:
pre_edit_budget_checkpoint_hit: yes/no
extra_pre_edit_reads_exception_recorded: yes/no/n/a
pre_edit_source_files_read_count:
pre_edit_source_snippets_read_count:
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
