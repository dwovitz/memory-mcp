# Codex Execution Prompt: Token-Budgeted Outline Benchmark Loop

Run this from:

```text
D:\git\ai\memory-mcp
```

You are executing the token-budgeted Outline benchmark loop for `memory-mcp`.
The goal is to run paired baseline and memory benchmarks against
`D:\git\ai\outline`, gather compact results, review the evidence, write a
focused fix prompt when the benchmark identifies a real `memory-mcp` product or
prompt failure, apply the fix only when justified, and rerun the affected case
to capture before/after evidence.

Do not turn this into an unbounded benchmark run. Start with `--mode targeted`,
use dry-run preflight before launching agents, and only use
`--allow-large-token-run` after writing down why the projected suite cost is
worth it. Use compact artifacts by default. Use `--keep-full-artifacts` only for
a specific debugging rerun where tails and parsed result JSON are insufficient.

## Preflight

1. Inspect the branch and working tree:

```powershell
git status --short --branch
```

Do not overwrite unrelated local changes. If unrelated dirty files would make
the benchmark invalid, stop and report the blocker.

2. Verify the benchmark runner contracts:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_outline_benchmark_runner.py tests\test_benchmark_cases.py -q
```

3. Run a token preflight without launching agents:

```powershell
$agentCommand = "codex exec --dangerously-bypass-approvals-and-sandbox"

.\.venv\Scripts\python.exe benchmarks\run_outline_benchmarks.py `
  --agent-command $agentCommand `
  --mode targeted `
  --cases outline_feature_update_collection_default_permissions,outline_feature_update_comment_resolution_audit `
  --variants baseline,memory `
  --iterations 2 `
  --dry-run
```

Review the preflight output. It must show each case, variant, iteration, mode,
estimated prompt tokens, per-case total-token budget, projected suite tokens,
and allowed/warned/skipped status.

If the dry run fails because projected suite tokens exceed the active mode
budget, do not immediately pass `--allow-large-token-run`. First reduce scope:
run one case, fewer variants, or `--iterations 1`. Use `--allow-large-token-run`
only after documenting why the larger run is necessary.

4. Check Docker availability if the loop may update the local instance:

```powershell
docker compose ps
```

If Docker is unavailable, continue without `--update-docker` and report
`docker_updated: no` with the exact failure.

## Main Run

Run the targeted loop over the complex feature-update cases:

```powershell
.\.venv\Scripts\python.exe benchmarks\run_outline_benchmarks.py `
  --agent-command $agentCommand `
  --mode targeted `
  --cases outline_feature_update_collection_default_permissions,outline_feature_update_comment_resolution_audit `
  --variants baseline,memory `
  --iterations 2 `
  --timeout-seconds 3600 `
  --apply-improvement-prompt `
  --update-docker
```

If Docker failed during preflight, rerun the same command without
`--update-docker`. If the suite budget blocks the run, narrow scope first. Use:

```powershell
--allow-large-token-run
```

only when the narrowed alternatives would not answer the benchmark question and
the expected token cost is acceptable.

The runner prints the latest run directory. Treat that directory as the source
of truth.

## Collate Results

Read compact artifacts first:

```text
benchmarks/results/runs/<latest>/summary.json
benchmarks/results/runs/<latest>/summary.md
benchmarks/results/runs/<latest>/<case-id>/<iteration>/<variant>/result.json
benchmarks/results/runs/<latest>/<case-id>/<iteration>/<variant>/raw-result-block.txt
benchmarks/results/runs/<latest>/<case-id>/<iteration>/<variant>/stdout-tail.txt
benchmarks/results/runs/<latest>/<case-id>/<iteration>/<variant>/stderr-tail.txt
benchmarks/results/runs/<latest>/improvement/<iteration>/result.json
benchmarks/results/runs/<latest>/improvement/<iteration>/stdout.txt
```

Create:

```text
benchmarks/results/runs/<latest>/collated-analysis.md
```

The collated analysis must include:

- Runner command and mode.
- Preflight projected suite tokens and whether the suite budget was obeyed.
- Cases, variants, and iterations run.
- Invalid, skipped, warned, or budget-failed runs and why.
- Estimated prompt tokens, actual total tokens when known, and
  token_budget_obeyed for each result.
- source_read_budget_obeyed for memory results.
- Whether memory improved, hurt, or had no visible effect for each case.
- Files changed by any improvement prompt.
- Docker update outcome.
- Focused tests run after any `memory-mcp` updates.
- Remaining follow-up work.

Do not read full transcripts unless compact artifacts are insufficient to
diagnose a specific failure. If full transcripts are needed, run a narrowed
debugging rerun with:

```powershell
--keep-full-artifacts
```

and cite the reason in `collated-analysis.md`.

## Review And Fix-Prompt Loop

After collating, decide whether the evidence shows a real `memory-mcp` failure:

- Product failure: memory retrieval, context packets, source-read contracts, or
  runner behavior caused the memory variant to perform worse or violate budget.
- Prompt failure: benchmark instructions were ambiguous, internally
  contradictory, or encouraged invalid source reads.
- No fix: differences are agent variance, Outline-side complexity, or
  inconclusive evidence.

If there is no clear failure, do not make code changes. Record the reason in
`collated-analysis.md`.

If there is a clear failure, create:

```text
benchmarks/results/runs/<latest>/fix-prompt.md
```

The fix prompt must be self-contained and include:

- The exact failing case and variant.
- Links or paths to `summary.json`, `collated-analysis.md`, and relevant
  `result.json` files.
- The smallest target area to inspect or change.
- Required tests to add or update before implementation.
- The rerun command for the affected case.
- The required final evidence block.

Then execute the fix prompt in the same repository only if the user has asked
you to continue with implementation. Use test-first discipline:

1. Add or update a focused failing test.
2. Run it and confirm the expected failure.
3. Implement the minimal change.
4. Rerun the focused test.
5. Rerun the benchmark contracts:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_outline_benchmark_runner.py tests\test_benchmark_cases.py -q
```

6. If Docker is available and the fix changes runtime behavior, update:

```powershell
docker compose build memory-mcp
docker compose up -d postgres
docker compose up -d memory-mcp
docker compose ps
```

7. Rerun the affected benchmark with `--mode targeted --iterations 1` and
append the rerun directory to `collated-analysis.md`.

Prefer a narrowed rerun:

```powershell
.\.venv\Scripts\python.exe benchmarks\run_outline_benchmarks.py `
  --agent-command $agentCommand `
  --mode targeted `
  --cases <affected-case-id> `
  --variants baseline,memory `
  --iterations 1 `
  --timeout-seconds 3600
```

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
mode:
dry_run_preflight:
allow_large_token_run_used: yes/no
keep_full_artifacts_used: yes/no
run_directory:
collated_analysis:
fix_prompt:
iterations_completed:
cases_run:
invalid_runs:
token_budget_failures:
memory_budget_failures:
improvements_made:
docker_updated: yes/no
rerun_directories:
tests_run:
remaining_followups:
```
