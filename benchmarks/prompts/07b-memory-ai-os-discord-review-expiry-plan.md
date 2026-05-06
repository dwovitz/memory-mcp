# Memory Benchmark Prompt: ai-os-discord Review Expiry Plan

Case id: `ai_os_discord_review_expiry_plan`
Variant: `memory`

Use the real ai-os-discord repository at `D:\git\ai\ai-os-discord` as the
source checkout. Create a fresh isolated worktree branched from `origin/main`:

```powershell
$source = "D:\git\ai\ai-os-discord"
$workspace = "D:\git\ai\ai-os-discord-benchmarks\ai_os_discord_review_expiry_plan\memory"
$branch = "benchmark/ai-os-discord-review-expiry-plan-memory"
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

Before reading source broadly, retrieve a `memory-mcp` context packet with:

```text
workspace="ai"
project="ai-os-discord"
component="bot"
request="Prepare to implement a change that makes ai-os-discord review expiry handling observable and testable, stopping after source inspection and a concrete change plan."
include_global=true
include_inherited=true
include_sensitive=false
max_tokens=1200
```

Use the packet to narrow source inspection, but do not answer from memory alone.
Actually inspect the implicated source and test files before planning. Track
`source_read_limits` and keep source reads bounded. Path enumeration alone is
not enough for this benchmark.

Get to the point where you could make a concrete code change, but do not edit
files and do not run an implementation.

Produce a concrete change plan with exact source files, test files, the behavior
you would change, and the command you would run to validate it. The plan must
include `ReviewExpiryService`, `ReviewOptions`, and a focused `dotnet test`
command.

End with this exact fenced block:

```text
BENCHMARK_RESULT
case_id: ai_os_discord_review_expiry_plan
project: ai-os-discord
variant: memory
worktree:
branch:
memory_used: yes
memory_context_quality:
memory_source_read_policy:
memory_source_read_budget_tokens:
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
