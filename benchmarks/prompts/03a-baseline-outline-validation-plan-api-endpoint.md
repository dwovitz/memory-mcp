# Baseline Benchmark Prompt: Outline Validation Planning

Case id: `outline_validation_plan_wrong_component_fallback`
Variant: `baseline`

Use the real Outline repository at `D:\git\ai\outline` as the source checkout.
Create a fresh isolated worktree branched from `origin/main`:

```powershell
$source = "D:\git\ai\outline"
$workspace = "D:\git\ai\outline-benchmarks\outline_validation_plan_wrong_component_fallback\baseline"
$branch = "benchmark/outline_validation_plan_wrong_component_fallback-baseline"
git -C $source fetch origin main
git -C $source worktree add -B $branch $workspace origin/main
Set-Location $workspace
```

If that worktree path already exists or is dirty, stop and choose a new empty
workspace path with a short timestamp suffix. Do not overwrite prior benchmark
results.

Task: Create a focused validation plan before changing authenticated Outline
API endpoint behavior.

Baseline rules:

- Do not call `memory-mcp` or use stored project memory.
- Use only the Outline repository, local source inspection, and normal project
  documentation available in the checkout.
- Keep track of files inspected so the result can be compared with the memory
  variant.
- Produce a concrete validation plan with the exact test surfaces, fixtures,
  and commands you would use. Do not implement code unless the user asks for
  the implementation after reviewing the plan.

End with this exact fenced block:

```text
BENCHMARK_RESULT
case_id: outline_validation_plan_wrong_component_fallback
project: outline
variant: baseline
worktree:
branch:
memory_used: no
memory_context_quality: n/a
memory_source_read_policy: n/a
memory_source_read_budget_tokens: n/a
files_inspected:
files_changed:
tests_or_commands_recommended:
outcome:
notes:
```
