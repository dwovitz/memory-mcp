# Baseline Benchmark Prompt: Outline Complex Feature Update

Case id: `outline_feature_update_comment_resolution_audit`
Variant: `baseline`
Complexity: `complex`

Use the real Outline repository at `D:\git\ai\outline` as the source checkout.
Create a fresh isolated worktree branched from `origin/main`:

```powershell
$source = "D:\git\ai\outline"
$workspace = "D:\git\ai\outline-benchmarks\outline_feature_update_comment_resolution_audit\baseline"
$branch = "benchmark/outline_feature_update_comment_resolution_audit-baseline"
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

Baseline rules:

- Baseline rules override repo/project AGENTS memory workflow for benchmark
  purposes.
- Do not call `memory-mcp` or use stored project memory.
- If local instructions would require memory during this baseline run, stop and
  report `benchmark_invalid: yes` instead of continuing with memory.
- Use only the Outline repository, local source inspection, and normal project
  documentation available in the checkout.
- Keep track of files inspected before editing so the result can be compared
  with the memory variant.
- If fast search is unavailable, use path-only fallback search first. Do not use
  fallback commands that dump broad source lines.
- Avoid whole-file formatting or line-ending rewrites unrelated to the fix.
  Prefer formatter checks first. If formatting is required, keep it limited to
  intentionally touched files.
- `formatting_churn: none` means no unrelated formatting or line-ending churn;
  `limited` means formatter changes are confined to intentionally touched hunks
  or files and small enough to review inline; `broad` means whole-file
  formatting, line-ending rewrites, or very large same-file diffs unrelated to
  the fix.

End with this exact fenced block:

```text
BENCHMARK_RESULT
case_id: outline_feature_update_comment_resolution_audit
project: outline
variant: baseline
worktree:
branch:
memory_used: no
memory_context_quality: n/a
memory_source_read_policy: n/a
memory_source_read_budget_tokens: n/a
benchmark_invalid: yes/no
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
