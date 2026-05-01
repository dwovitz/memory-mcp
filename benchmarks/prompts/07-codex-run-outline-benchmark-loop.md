# Codex Execution Prompt: Run Outline Benchmark Loop

Run this from:

```text
D:\git\ai\memory-mcp
```

You are executing the automated Outline benchmark loop for `memory-mcp` in
Codex. The goal is to run the benchmark suite against `D:\git\ai\outline`,
collate the results, make targeted `memory-mcp` updates when the results show a
clear product or prompt failure, update the Docker-backed instance, and rerun so
the result directory contains before/after evidence.

## Preflight

1. Inspect the current branch and working tree:

```powershell
git status --short --branch
```

Do not overwrite unrelated local changes. If unrelated dirty files would make
the benchmark invalid, stop and report the blocker.

2. Verify the runner and benchmark contracts:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_outline_benchmark_runner.py tests\test_benchmark_cases.py -q
```

3. Verify the runner can plan at least one complex feature-update benchmark
without launching an agent:

```powershell
.\.venv\Scripts\python.exe benchmarks\run_outline_benchmarks.py --agent-command fake-agent --cases outline_feature_update_collection_default_permissions --variants baseline --iterations 1 --dry-run
```

4. Check Docker availability before requesting Docker updates:

```powershell
docker compose ps
```

If Docker is unavailable, continue the benchmark run without `--update-docker`
and report `docker_updated: no` with the exact failure.

## Agent Command

Use a real Codex non-interactive command for `--agent-command`. Start with:

```powershell
$agentCommand = "codex exec --dangerously-bypass-approvals-and-sandbox"
```

If this command cannot run in the local shell, do not silently substitute broad
manual execution. Stop and report the access or command failure unless the user
has already provided a different agent command.

## Benchmark Loop

Run the automated loop over the complex feature-update cases first. This should
run baseline and memory variants, apply the improvement prompt after iteration
1, update Docker, then run iteration 2:

```powershell
.\.venv\Scripts\python.exe benchmarks\run_outline_benchmarks.py `
  --agent-command $agentCommand `
  --cases outline_feature_update_collection_default_permissions,outline_feature_update_comment_resolution_audit `
  --variants baseline,memory `
  --iterations 2 `
  --timeout-seconds 3600 `
  --apply-improvement-prompt `
  --update-docker
```

If Docker failed during preflight, rerun the same command without
`--update-docker`.

The runner prints the latest run directory. Treat that directory as the source
of truth for collation.

## Collate Results

Read the latest run artifacts:

```text
benchmarks/results/runs/<latest>/summary.json
benchmarks/results/runs/<latest>/summary.md
benchmarks/results/runs/<latest>/<case-id>/<iteration>/<variant>/result.json
benchmarks/results/runs/<latest>/<case-id>/<iteration>/<variant>/stdout.txt
benchmarks/results/runs/<latest>/improvement/<iteration>/stdout.txt
```

Create:

```text
benchmarks/results/runs/<latest>/collated-analysis.md
```

The collated analysis must include:

- Cases and variants run.
- Invalid runs and why they were invalid.
- Memory source-read budget compliance before and after improvement.
- Whether memory improved, hurt, or had no visible effect on each complex
  feature-update case.
- Files changed by any improvement prompt.
- Docker update outcome.
- Focused test results after any `memory-mcp` updates.
- Remaining follow-up work.

## Make Updates

If the benchmark results show a clear `memory-mcp` product or prompt failure,
make the smallest targeted update. Follow test-first discipline:

1. Add or update a focused failing test that captures the failure.
2. Run that test and confirm it fails for the expected reason.
3. Implement the minimal change.
4. Rerun the focused test.
5. Rerun:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_outline_benchmark_runner.py tests\test_benchmark_cases.py tests\test_context_synthesis.py tests\test_mcp_tools.py -q
```

6. If Docker is available, update the local instance:

```powershell
docker compose build memory-mcp
docker compose up -d postgres
docker compose up -d memory-mcp
docker compose ps
```

7. Rerun the benchmark loop for the affected case or cases with
`--iterations 1` and append the rerun directory to `collated-analysis.md`.

Do not make broad retrieval rewrites unless the collated evidence directly
requires them. Preserve sensitive/private memory gating and component fallback
behavior.

## Final Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Then inspect:

```powershell
git status --short
git diff --stat
```

End with this exact fenced block:

```text
BENCHMARK_LOOP_RESULT
project: memory-mcp
runner_command:
run_directory:
collated_analysis:
iterations_completed:
cases_run:
invalid_runs:
memory_budget_failures:
improvements_made:
docker_updated: yes/no
rerun_directories:
tests_run:
remaining_followups:
```
