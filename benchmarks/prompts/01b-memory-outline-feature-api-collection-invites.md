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

Avoid whole-file formatting or line-ending rewrites unrelated to the fix. Prefer
formatter checks first. If formatting is required, keep it limited to
intentionally touched files and call out any broad formatter churn in notes.

End with this exact fenced block:

```text
BENCHMARK_RESULT
case_id: outline_feature_api_collection_invites
project: outline
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
files_inspected_before_edit:
files_changed:
formatting_churn: none/limited/broad
tests_run:
outcome:
notes:
```
