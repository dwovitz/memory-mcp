# Baseline Benchmark Prompt: Outline Bug Fix

Case id: `outline_bug_fix_search_authorization`
Variant: `baseline`

Use the real Outline repository at `D:\git\ai\outline` as the source checkout.
Create a fresh isolated worktree branched from `origin/main`:

```powershell
$source = "D:\git\ai\outline"
$workspace = "D:\git\ai\outline-benchmarks\outline_bug_fix_search_authorization\baseline"
$branch = "benchmark/outline_bug_fix_search_authorization-baseline"
git -C $source fetch origin main
git -C $source worktree add -B $branch $workspace origin/main
Set-Location $workspace
```

If that worktree path already exists or is dirty, stop and choose a new empty
workspace path with a short timestamp suffix. Do not overwrite prior benchmark
results.

Task: Fix an Outline search API bug that returns private document titles.

Baseline rules:

- Do not call `memory-mcp` or use stored project memory.
- Use only the Outline repository, local source inspection, and normal project
  documentation available in the checkout.
- Keep track of files inspected before editing so the result can be compared
  with the memory variant.
- Make the smallest coherent fix and focused tests you can justify from the
  codebase.
- Avoid whole-file formatting or line-ending rewrites unrelated to the fix.
  Prefer formatter checks first. If formatting is required, keep it limited to
  intentionally touched files and call out any broad formatter churn in notes.

End with this exact fenced block:

```text
BENCHMARK_RESULT
case_id: outline_bug_fix_search_authorization
project: outline
variant: baseline
worktree:
branch:
memory_used: no
memory_context_quality: n/a
memory_source_read_policy: n/a
memory_source_read_budget_tokens: n/a
files_inspected_before_edit:
files_changed:
formatting_churn: none/limited/broad
tests_run:
outcome:
notes:
```
