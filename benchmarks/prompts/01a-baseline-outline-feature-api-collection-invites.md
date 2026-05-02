# Baseline Benchmark Prompt: Outline Feature Work

Case id: `outline_feature_api_collection_invites`
Variant: `baseline`

Use the real Outline repository at `D:\git\ai\outline` as the source checkout.
Create a fresh isolated worktree branched from `origin/main`:

```powershell
$source = "D:\git\ai\outline"
$workspace = "D:\git\ai\outline-benchmarks\outline_feature_api_collection_invites\baseline"
$branch = "benchmark/outline_feature_api_collection_invites-baseline"
git -C $source fetch origin main
git -C $source worktree add -B $branch $workspace origin/main
Set-Location $workspace
```

If that worktree path already exists or is dirty, stop and choose a new empty
workspace path with a short timestamp suffix. Do not overwrite prior benchmark
results.

Task: Implement collection-level invite expiration settings in the Outline API.

Baseline rules:

- Baseline rules override repo/project AGENTS memory workflow for benchmark
  purposes.
- Do not call `memory-mcp` or use stored project memory.
- If local instructions would require memory during this baseline run, stop and report the run as invalid instead of continuing with memory.
- Use only the Outline repository, local source inspection, and normal project
  documentation available in the checkout.
- Keep track of files inspected before editing so the result can be compared
  with the memory variant.
- Make the smallest coherent implementation and focused tests you can justify
  from the codebase.
- Avoid whole-file formatting or line-ending rewrites unrelated to the fix.
  Prefer formatter checks first. If formatting is required, keep it limited to
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
variant: baseline
worktree:
branch:
benchmark_invalid: yes/no
memory_used: no
memory_context_quality: n/a
memory_source_read_policy: n/a
memory_source_read_budget_tokens: n/a
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
