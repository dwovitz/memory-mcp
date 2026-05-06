# Baseline Benchmark Prompt: ai-os-discord Review Expiry Plan

Case id: `ai_os_discord_review_expiry_plan`
Variant: `baseline`

Use the real ai-os-discord repository at `D:\git\ai\ai-os-discord` as the
source checkout. Create a fresh isolated worktree branched from `origin/main`:

```powershell
$source = "D:\git\ai\ai-os-discord"
$workspace = "D:\git\ai\ai-os-discord-benchmarks\ai_os_discord_review_expiry_plan\baseline"
$branch = "benchmark/ai-os-discord-review-expiry-plan-baseline"
git -C $source fetch origin main
git -C $source worktree add -B $branch $workspace origin/main
Set-Location $workspace
```

If that worktree path already exists or is dirty, stop and choose a new empty
workspace path with a short timestamp suffix. Do not overwrite prior benchmark
results.

Task: Prepare to implement a change that makes review expiry handling
observable and testable, stopping after source inspection and a concrete change
plan.

Baseline rules:

- Do not call `memory-mcp` or use stored project memory.
- Use only the ai-os-discord repository, local source inspection, and normal
  project documentation available in the checkout.
- Actually inspect source files before planning. Path enumeration alone is not
  enough for this benchmark.
- Get to the point where you could make a concrete code change, but do not edit
  files and do not run an implementation.
- Track files inspected so the result can be compared with the memory variant.

Produce a concrete change plan with exact source files, test files, the behavior
you would change, and the command you would run to validate it. The plan must
include `ReviewExpiryService`, `ReviewOptions`, and a focused `dotnet test`
command.

End with this exact fenced block:

```text
BENCHMARK_RESULT
case_id: ai_os_discord_review_expiry_plan
project: ai-os-discord
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
