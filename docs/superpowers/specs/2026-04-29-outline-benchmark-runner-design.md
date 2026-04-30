# Outline Benchmark Runner Design

## Purpose

Create a fully automated runner for the existing Outline benchmark prompt suite.
The runner should exercise `memory-mcp` against the real Outline checkout at
`D:\git\ai\outline`, collect baseline and memory-agent outputs, detect invalid
runs, optionally apply improvement prompts, update the local Docker-backed
`memory-mcp` instance, and rerun benchmarks for comparison.

The first implementation should automate orchestration and artifact capture
without embedding assumptions about a single model vendor or agent CLI.

## Current Context

The repository already contains task-oriented benchmark data:

- `benchmarks/cases.json` defines Outline benchmark cases, scoped memories, and
  expected context-packet behavior.
- `benchmarks/prompts/` contains paired baseline and memory prompts for each
  case, plus product improvement prompts.
- `benchmarks/results/` contains manually saved benchmark outputs and
  comparisons.
- `tests/test_benchmark_cases.py` validates prompt contracts and context-packet
  behavior.

The missing piece is an executable loop that can run the prompt suite,
persist artifacts, summarize results, update the Docker instance, and repeat.

## Recommended Approach

Add a Python runner script under `benchmarks/` with a configurable agent command.
The script should run on Windows PowerShell-friendly paths but avoid depending
on PowerShell-specific parsing for core behavior.

The runner is invoked with an explicit command template, for example:

```powershell
python benchmarks/run_outline_benchmarks.py `
  --outline-repo D:\git\ai\outline `
  --agent-command "codex exec --dangerously-bypass-approvals-and-sandbox" `
  --variants baseline,memory `
  --iterations 2 `
  --update-docker `
  --apply-improvement-prompt
```

The runner should fail clearly when the configured agent command cannot be
executed. Direct Codex execution is not assumed to work in all environments.

## Scope

### In Scope

- Discover benchmark cases from `benchmarks/cases.json`.
- Validate that the prompt suite contains a meaningful mix of benchmark task
  types, including complex feature-update cases.
- Resolve benchmark prompt files from `benchmarks/prompts/`.
- Run selected variants for selected cases through a subprocess agent command.
- Pass prompt text through standard input by default.
- Capture stdout, stderr, exit code, start time, end time, duration, and command
  metadata.
- Extract the final fenced `BENCHMARK_RESULT` block from agent output.
- Parse result block fields into JSON.
- Mark a run invalid when required fields are missing or contradictory.
- Specifically mark baseline runs invalid when `memory_used: yes`.
- Save raw logs and parsed results under a timestamped run directory.
- Generate per-iteration JSON and Markdown summaries.
- Optionally run the product improvement prompt after benchmark comparisons.
- Optionally rebuild/restart the local Docker-backed `memory-mcp` services.
- Support multiple iterations so improvements can be applied and rerun.
- Add automated tests around parser behavior, prompt discovery, invalid-run
  detection, and subprocess orchestration with a fake agent command.

### Out Of Scope

- Implementing or changing memory retrieval ranking.
- Changing Outline source code directly from the runner.
- Hard-coding a specific model or account configuration.
- Automatically approving unsafe agent operations.
- Replacing the existing context synthesis tests.
- Performing a real agent/model benchmark inside unit tests.

## Command Model

The runner should accept `--agent-command` as a command string. It should split
the command with platform-aware shell parsing and append no implicit flags except
those documented by the runner. Prompt text should be sent to the subprocess on
stdin.

Each run should use a timeout. A timeout should terminate the subprocess, save
partial logs, and mark the benchmark run invalid with a timeout reason.

The runner should support a `--dry-run` mode that prints planned runs without
executing the agent command.

## Artifact Layout

Write all generated artifacts under:

```text
benchmarks/results/runs/<timestamp>/
```

Suggested files:

```text
metadata.json
summary.json
summary.md
<case-id>/<iteration>/<variant>/prompt.md
<case-id>/<iteration>/<variant>/stdout.txt
<case-id>/<iteration>/<variant>/stderr.txt
<case-id>/<iteration>/<variant>/result.json
<case-id>/<iteration>/<variant>/raw-result-block.txt
```

This keeps generated run output separate from the curated comparison files
already stored directly under `benchmarks/results/`.

## Result Parsing

The parser should find the last `BENCHMARK_RESULT` block in stdout. It should
accept both fenced and unfenced blocks because agent formatting can vary, but
the prompts should continue to request the fenced format.

Parsed fields are simple `key: value` lines. Multi-line values are not needed
for the first version; the runner can preserve raw output for detailed notes.

Required fields:

- `case_id`
- `project`
- `variant`
- `worktree`
- `branch`
- `memory_used`
- `files_changed`
- `tests_run`
- `outcome`

Memory variants should also require:

- `memory_context_quality`
- `memory_source_read_policy`
- `memory_source_read_budget_tokens`
- `source_read_budget_obeyed`
- `source_files_read_count`
- `source_snippets_read_count`

The runner should record validation errors rather than discarding runs.

## Benchmark Case Mix

The suite should deliberately include feature-update work, especially cases that
are complex enough to show whether memory helps the agent form a correct plan
before touching source. The prompt suite should not drift into only bug fixes,
validation plans, or simple single-file edits.

At minimum, the benchmark metadata should contain:

- At least one existing feature-work case.
- At least two complex feature-update cases.
- At least one bug-fix case.
- At least one validation-planning case.

Complex feature-update cases should involve multiple repository boundaries. Good
Outline examples include API contract changes that touch validation, policy
checks, persistence, presenters, and focused tests; or product behavior changes
that span server routes, models or commands, and client-visible response shape.

Complex feature-update cases should be marked in `cases.json` with enough
metadata for tests and summaries to identify them, for example:

```json
{
  "category": "feature_update",
  "complexity": "complex",
  "touchpoints": ["api", "authorization", "persistence", "tests"]
}
```

The runner should surface category and complexity in `summary.json` and
`summary.md` so comparisons can answer whether memory helped on substantial
feature work, not only on safer planning or bug-fix prompts.

## Docker Update Loop

When `--update-docker` is set, the runner should update the local Docker-backed
`memory-mcp` instance between iterations or after applying an improvement prompt.

Default sequence:

```powershell
docker compose build memory-mcp
docker compose up -d postgres
docker compose up -d memory-mcp
docker compose ps
```

The runner should save stdout/stderr for each Docker command. Docker failures
should stop further benchmark execution unless `--continue-on-docker-failure` is
explicitly set.

## Improvement Prompt Loop

When `--apply-improvement-prompt` is set, the runner should run a configured
improvement prompt after baseline/memory comparisons for an iteration.

The default improvement prompt should be the existing strict fallback prompt:

```text
benchmarks/prompts/04-memory-mcp-implementation-prompt-strict-fallback-and-baseline-isolation.md
```

After running an improvement prompt, the runner should:

1. Save the improvement agent logs.
2. Run the requested project tests if configured.
3. Update Docker when `--update-docker` is enabled.
4. Start the next benchmark iteration.

The runner should not assume that the improvement prompt produced code changes.
It should record git status before and after the improvement run.

## Safety And Invalid Runs

The runner should never overwrite existing run directories. Timestamped
directories avoid collisions, and if a collision is still detected the runner
should append a short numeric suffix.

Baseline prompts must remain isolated from memory. If a baseline result reports
`memory_used: yes`, the run is invalid for comparison.

If an agent exits non-zero but still prints a result block, the run should be
recorded as completed-with-error rather than silently dropped.

## Tests

Use test-first implementation for production runner code.

Initial tests should cover:

- Discovering baseline and memory prompt files for every case.
- Verifying the benchmark case set includes complex feature-update cases.
- Selecting cases and variants from CLI arguments.
- Parsing a valid fenced `BENCHMARK_RESULT` block.
- Parsing the last result block when multiple blocks appear.
- Reporting missing required fields.
- Marking baseline `memory_used: yes` as invalid.
- Marking timeout and subprocess failures as invalid while preserving logs.
- Building artifact paths without overwriting existing run directories.
- Running a fake agent command that echoes a result block.
- Dry-run mode producing a plan without executing subprocesses.

The tests should not call real Codex, Docker, or Outline commands.

## Open Decisions

- The default timeout should start conservatively, likely 60 minutes per agent
  run, with a CLI override.
- The first version can require `--agent-command`; a later version can add
  named presets such as `--agent codex`.
- Comparison scoring should initially be descriptive rather than judgmental:
  memory budget obeyed, invalid run count, files inspected, files changed,
  tests run, and outcome.
