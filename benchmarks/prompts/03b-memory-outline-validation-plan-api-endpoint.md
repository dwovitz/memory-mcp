# Memory Benchmark Prompt: Outline Validation Planning

Case id: `outline_validation_plan_wrong_component_fallback`
Variant: `memory`

Use the real Outline repository at `D:\git\ai\outline` as the source checkout.
Create a fresh isolated worktree branched from `origin/main`:

```powershell
$source = "D:\git\ai\outline"
$workspace = "D:\git\ai\outline-benchmarks\outline_validation_plan_wrong_component_fallback\memory"
$branch = "benchmark/outline_validation_plan_wrong_component_fallback-memory"
git -C $source fetch origin main
git -C $source worktree add -B $branch $workspace origin/main
Set-Location $workspace
```

If that worktree path already exists or is dirty, stop and choose a new empty
workspace path with a short timestamp suffix. Do not overwrite prior benchmark
results.

Task: Create a focused validation plan before changing authenticated Outline
API endpoint behavior.

Before reading source broadly, retrieve a `memory-mcp` context packet with:

```text
workspace="ai"
project="outline"
component="tests"
request="Create a focused validation plan before changing authenticated Outline API endpoint behavior."
include_global=true
include_inherited=true
include_sensitive=false
max_tokens=1200
```

This case intentionally asks from the `tests` component even when the strongest
stored context may be in the `api` component. If the packet reports a usable
fallback, use that result and verify narrowly instead of reading broad source.
Use `source_read_limits` to track how many source files and snippets you read.
If fast search such as `rg` is unavailable, enumerate paths and inspect targeted
snippets instead of dumping broad recursive search output.

Produce a concrete validation plan with the exact test surfaces, fixtures, and
commands you would use. Do not implement code unless the user asks for the
implementation after reviewing the plan.

End with this exact fenced block:

```text
BENCHMARK_RESULT
case_id: outline_validation_plan_wrong_component_fallback
project: outline
variant: memory
worktree:
branch:
memory_used: yes
memory_context_quality:
memory_source_read_policy:
memory_source_read_budget_tokens:
fallback_accepted: yes/no
source_read_budget_obeyed: yes/no
source_files_read_count:
source_snippets_read_count:
source_budget_exception:
files_inspected:
files_changed:
tests_or_commands_recommended:
outcome:
notes:
```
