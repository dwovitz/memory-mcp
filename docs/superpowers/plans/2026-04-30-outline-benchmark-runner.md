# Outline Benchmark Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python runner that executes Outline benchmark prompts through a configurable agent command, records artifacts, validates result blocks, supports Docker update loops, and ensures the suite includes complex feature-update cases.

**Architecture:** Put reusable runner logic in `benchmarks/outline_benchmark_runner.py` and keep `benchmarks/run_outline_benchmarks.py` as a thin CLI wrapper. Extend `benchmarks/cases.json` and `benchmarks/prompts/` with complex feature-update cases. Add pytest coverage in `tests/test_outline_benchmark_runner.py` and update benchmark contract tests in `tests/test_benchmark_cases.py`.

**Tech Stack:** Python 3.12 standard library, pytest, JSON benchmark metadata, Markdown prompt files, subprocess orchestration.

---

### Task 1: Result Parser And Validation

**Files:**
- Create: `benchmarks/outline_benchmark_runner.py`
- Create: `tests/test_outline_benchmark_runner.py`

- [ ] **Step 1: Write failing parser tests**

Add tests that import `parse_benchmark_result` and `validate_result`.

```python
def test_parse_benchmark_result_uses_last_fenced_block() -> None:
    output = """
BENCHMARK_RESULT
case_id: old
```
BENCHMARK_RESULT
case_id: outline_feature
project: outline
variant: baseline
worktree: D:\\git\\ai\\outline-benchmarks\\case\\baseline
branch: benchmark/case-baseline
memory_used: no
files_changed: server/routes/api.ts
tests_run: yarn test server/routes/api.test.ts
outcome: completed
```
"""

    parsed = parse_benchmark_result(output)

    assert parsed.block_text.startswith("BENCHMARK_RESULT")
    assert parsed.fields["case_id"] == "outline_feature"
    assert parsed.fields["variant"] == "baseline"


def test_validate_result_rejects_baseline_that_used_memory() -> None:
    parsed = ParsedBenchmarkResult(
        fields={
            "case_id": "outline_feature",
            "project": "outline",
            "variant": "baseline",
            "worktree": "D:\\git\\ai\\outline-benchmarks\\case\\baseline",
            "branch": "benchmark/case-baseline",
            "memory_used": "yes",
            "files_changed": "server/routes/api.ts",
            "tests_run": "yarn test server/routes/api.test.ts",
            "outcome": "completed",
        },
        block_text="BENCHMARK_RESULT",
    )

    validation = validate_result(parsed)

    assert validation.valid is False
    assert "baseline reported memory_used: yes" in validation.errors
```

- [ ] **Step 2: Run parser tests to verify failure**

Run: `python -m pytest tests/test_outline_benchmark_runner.py -q`

Expected: import failure because `benchmarks.outline_benchmark_runner` does not exist.

- [ ] **Step 3: Implement parser and validation**

Create dataclasses `ParsedBenchmarkResult` and `ResultValidation`. Implement `parse_benchmark_result(output: str) -> ParsedBenchmarkResult` and `validate_result(parsed: ParsedBenchmarkResult) -> ResultValidation`.

- [ ] **Step 4: Run parser tests to verify pass**

Run: `python -m pytest tests/test_outline_benchmark_runner.py -q`

Expected: parser tests pass.

### Task 2: Case Discovery And Complex Feature Metadata

**Files:**
- Modify: `benchmarks/cases.json`
- Create: `benchmarks/prompts/05a-baseline-outline-feature-update-collection-default-permissions.md`
- Create: `benchmarks/prompts/05b-memory-outline-feature-update-collection-default-permissions.md`
- Create: `benchmarks/prompts/06a-baseline-outline-feature-update-comment-resolution-audit.md`
- Create: `benchmarks/prompts/06b-memory-outline-feature-update-comment-resolution-audit.md`
- Modify: `tests/test_benchmark_cases.py`
- Modify: `tests/test_outline_benchmark_runner.py`

- [ ] **Step 1: Write failing metadata tests**

Add a test that loads `benchmarks/cases.json` and asserts at least two cases have `category == "feature_update"` and `complexity == "complex"`, each with at least three `touchpoints`.

- [ ] **Step 2: Run metadata tests to verify failure**

Run: `python -m pytest tests/test_benchmark_cases.py::test_benchmark_cases_include_complex_feature_updates -q`

Expected: failure because the complex feature-update cases do not exist yet.

- [ ] **Step 3: Add two complex feature-update cases**

Append two cases to `benchmarks/cases.json`:

- `outline_feature_update_collection_default_permissions`
- `outline_feature_update_comment_resolution_audit`

Each case should include baseline/memory prompt pairs, realistic scoped memories, expected packet behavior, `complexity: "complex"`, and `touchpoints` spanning API, authorization, persistence, presenters or events, and tests.

- [ ] **Step 4: Add prompt pairs**

Create baseline and memory prompts matching existing prompt style. Each prompt must create an isolated Outline worktree, run from `D:\git\ai\outline`, require `BENCHMARK_RESULT`, include invalid-run handling fields, fallback-search fields, and formatting churn definitions.

- [ ] **Step 5: Update prompt contract tests**

Adjust prompt count assertions so non-04 benchmark prompts equal `len(cases) * 2`. Add assertions that complex feature-update prompts mention multi-boundary work and include `complexity: complex` or equivalent wording.

- [ ] **Step 6: Run benchmark contract tests**

Run: `python -m pytest tests/test_benchmark_cases.py -q`

Expected: benchmark contract tests pass.

### Task 3: Runner Planning, Dry Run, And Artifact Paths

**Files:**
- Modify: `benchmarks/outline_benchmark_runner.py`
- Modify: `tests/test_outline_benchmark_runner.py`

- [ ] **Step 1: Write failing dry-run and selection tests**

Add tests for `load_cases`, `select_cases`, `select_variants`, `build_run_plan`, and `create_run_directory`. The tests should use temporary directories and avoid real Outline, Docker, or agent commands.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_outline_benchmark_runner.py -q`

Expected: failures for missing planning functions.

- [ ] **Step 3: Implement planning functions**

Implement:

- `load_cases(cases_path: Path) -> list[dict[str, Any]]`
- `select_cases(cases, requested_ids)`
- `select_variants(value: str) -> list[str]`
- `discover_prompt(case_id, variant, prompts_dir) -> Path`
- `build_run_plan(...) -> list[PlannedRun]`
- `create_run_directory(results_dir, timestamp=None) -> Path`

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_outline_benchmark_runner.py -q`

Expected: all runner unit tests pass so far.

### Task 4: Subprocess Runner And Summaries

**Files:**
- Modify: `benchmarks/outline_benchmark_runner.py`
- Create: `benchmarks/run_outline_benchmarks.py`
- Modify: `tests/test_outline_benchmark_runner.py`

- [ ] **Step 1: Write failing subprocess tests**

Add a fake Python agent command test that reads prompt text from stdin and prints a valid `BENCHMARK_RESULT`. Assert the runner saves `prompt.md`, `stdout.txt`, `stderr.txt`, `raw-result-block.txt`, and `result.json`.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_outline_benchmark_runner.py -q`

Expected: failures for missing execution functions.

- [ ] **Step 3: Implement subprocess execution**

Implement `run_agent`, `write_run_artifacts`, `run_planned_benchmark`, `write_summary_json`, and `write_summary_markdown`. Capture command, exit code, start/end timestamps, duration, parsed result, validation errors, and metadata category/complexity.

- [ ] **Step 4: Add CLI wrapper**

Implement `benchmarks/run_outline_benchmarks.py` with argparse flags:

- `--outline-repo`
- `--agent-command`
- `--cases`
- `--variants`
- `--iterations`
- `--results-dir`
- `--timeout-seconds`
- `--dry-run`
- `--update-docker`
- `--continue-on-docker-failure`
- `--apply-improvement-prompt`
- `--improvement-prompt`

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/test_outline_benchmark_runner.py -q`

Expected: runner tests pass.

### Task 5: Docker And Improvement Prompt Loop

**Files:**
- Modify: `benchmarks/outline_benchmark_runner.py`
- Modify: `tests/test_outline_benchmark_runner.py`

- [ ] **Step 1: Write failing Docker/improvement tests**

Add tests that inject a fake command runner and verify Docker command order:

```text
docker compose build memory-mcp
docker compose up -d postgres
docker compose up -d memory-mcp
docker compose ps
```

Add a test that an improvement prompt is planned after an iteration when enabled.

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_outline_benchmark_runner.py -q`

Expected: failures for missing Docker/improvement orchestration.

- [ ] **Step 3: Implement Docker and improvement orchestration**

Implement `run_docker_update` and iteration orchestration. Docker failures stop execution unless `continue_on_docker_failure` is true. Improvement prompt runs through the same agent command and stores artifacts under `improvement/<iteration>/`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_outline_benchmark_runner.py -q`

Expected: runner tests pass.

### Task 6: Verification And Closeout

**Files:**
- Modify as needed from earlier tasks only.

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_outline_benchmark_runner.py tests/test_benchmark_cases.py -q`

Expected: pass.

- [ ] **Step 2: Run context synthesis regression tests**

Run: `python -m pytest tests/test_context_synthesis.py tests/test_mcp_tools.py -q`

Expected: pass.

- [ ] **Step 3: Run full suite**

Run: `python -m pytest -q`

Expected: pass, or report exact pre-existing failures if any.

- [ ] **Step 4: Inspect final git diff**

Run: `git status --short` and `git diff --stat`.

Expected: only benchmark runner, tests, prompt, and benchmark metadata changes from this work plus pre-existing user changes.

