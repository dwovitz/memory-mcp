"""Automated runner utilities for Outline memory benchmarks."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import ctypes
from ctypes import POINTER, byref, c_int, c_wchar_p
from ctypes import wintypes
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


REQUIRED_RESULT_FIELDS = (
    "case_id",
    "project",
    "variant",
    "worktree",
    "branch",
    "memory_used",
    "files_changed",
    "tests_run",
    "outcome",
)
MEMORY_RESULT_FIELDS = (
    "memory_context_quality",
    "memory_source_read_policy",
    "memory_source_read_budget_tokens",
    "source_read_budget_obeyed",
    "source_files_read_count",
    "source_snippets_read_count",
)
RUN_MODES = ("smoke", "targeted", "full")
STDOUT_TAIL_CHARACTERS = 12_000
STDERR_TAIL_CHARACTERS = 12_000


@dataclass(frozen=True)
class BudgetProfile:
    """Token and source-read limits used for one benchmark mode."""

    max_prompt_tokens: int
    max_completion_tokens: int
    max_total_tokens: int
    max_total_run_tokens: int
    max_source_files_before_edit: int
    max_snippets_before_edit: int

    def replace(self, **changes: int) -> "BudgetProfile":
        return replace(self, **changes)


DEFAULT_BUDGET_PROFILES: dict[str, BudgetProfile] = {
    "smoke": BudgetProfile(
        max_prompt_tokens=12_000,
        max_completion_tokens=18_000,
        max_total_tokens=25_000,
        max_total_run_tokens=50_000,
        max_source_files_before_edit=4,
        max_snippets_before_edit=8,
    ),
    "targeted": BudgetProfile(
        max_prompt_tokens=24_000,
        max_completion_tokens=40_000,
        max_total_tokens=64_000,
        max_total_run_tokens=160_000,
        max_source_files_before_edit=8,
        max_snippets_before_edit=16,
    ),
    "full": BudgetProfile(
        max_prompt_tokens=60_000,
        max_completion_tokens=100_000,
        max_total_tokens=160_000,
        max_total_run_tokens=320_000,
        max_source_files_before_edit=16,
        max_snippets_before_edit=32,
    ),
}


@dataclass(frozen=True)
class ParsedBenchmarkResult:
    """Parsed BENCHMARK_RESULT fields and the raw block text."""

    fields: dict[str, str]
    block_text: str


@dataclass(frozen=True)
class ResultValidation:
    """Validation status for a parsed benchmark result."""

    valid: bool
    errors: list[str]


@dataclass(frozen=True)
class PlannedRun:
    """One benchmark prompt execution planned by the runner."""

    case_id: str
    variant: str
    iteration: int
    prompt_path: Path
    category: str
    complexity: str | None
    touchpoints: list[str]
    mode: str
    budget: BudgetProfile
    estimated_prompt_tokens: int
    projected_total_tokens: int


@dataclass(frozen=True)
class TokenMetrics:
    """Estimated and actual token-budget accounting for one run."""

    estimated_prompt_tokens: int
    actual_input_tokens: int | None
    actual_output_tokens: int | None
    actual_total_tokens: int | None
    token_budget_obeyed: str
    token_budget_exception: str


@dataclass(frozen=True)
class PreflightItem:
    """Preflight status for one planned benchmark run."""

    planned: PlannedRun
    status: str
    reason: str


@dataclass(frozen=True)
class PreflightPlan:
    """Preflight status for a suite of benchmark runs."""

    items: list[PreflightItem]
    projected_suite_tokens: int
    max_total_run_tokens: int
    suite_budget_obeyed: bool


@dataclass(frozen=True)
class AgentExecution:
    """Raw subprocess execution details."""

    command: list[str]
    stdout: str
    stderr: str
    exit_code: int | None
    timed_out: bool
    started_at: str
    ended_at: str
    duration_seconds: float


@dataclass(frozen=True)
class BenchmarkRunResult:
    """Complete benchmark run result and artifact location."""

    planned: PlannedRun
    artifact_dir: Path
    execution: AgentExecution
    parsed: ParsedBenchmarkResult
    validation: ResultValidation
    token_metrics: TokenMetrics


def parse_benchmark_result(output: str) -> ParsedBenchmarkResult:
    """Parse the final BENCHMARK_RESULT block from agent output."""

    marker = "BENCHMARK_RESULT"
    start = output.rfind(marker)
    if start == -1:
        return ParsedBenchmarkResult(fields={}, block_text="")

    remainder = output[start:]
    closing_fence = remainder.find("```", len(marker))
    block_text = remainder if closing_fence == -1 else remainder[:closing_fence]
    block_text = block_text.strip()

    fields: dict[str, str] = {}
    for raw_line in block_text.splitlines():
        line = raw_line.strip()
        if not line or line == marker or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()

    return ParsedBenchmarkResult(fields=fields, block_text=block_text)


def validate_result(parsed: ParsedBenchmarkResult) -> ResultValidation:
    """Validate required benchmark result fields and variant-specific rules."""

    errors: list[str] = []
    if not parsed.block_text:
        errors.append("missing BENCHMARK_RESULT block")

    for field in REQUIRED_RESULT_FIELDS:
        if not parsed.fields.get(field):
            errors.append(f"missing required field: {field}")

    variant = parsed.fields.get("variant", "").lower()
    memory_used = parsed.fields.get("memory_used", "").lower()
    if variant == "baseline" and memory_used == "yes":
        errors.append("baseline reported memory_used: yes")

    if variant == "memory":
        for field in MEMORY_RESULT_FIELDS:
            if not parsed.fields.get(field):
                errors.append(f"missing memory field: {field}")

    return ResultValidation(valid=not errors, errors=errors)


def load_cases(cases_path: Path) -> list[dict[str, Any]]:
    """Load benchmark case metadata from JSON."""

    return json.loads(cases_path.read_text(encoding="utf-8"))


def select_cases(cases: list[dict[str, Any]], requested_ids: list[str] | None) -> list[dict[str, Any]]:
    """Filter cases by id while preserving file order."""

    if not requested_ids:
        return cases
    requested = set(requested_ids)
    selected = [case for case in cases if case["id"] in requested]
    missing = requested - {case["id"] for case in selected}
    if missing:
        raise ValueError("unknown case id: " + ", ".join(sorted(missing)))
    return selected


def select_variants(value: str) -> list[str]:
    """Parse and validate a comma-separated variant list."""

    variants = [part.strip() for part in value.split(",") if part.strip()]
    allowed = {"baseline", "memory"}
    for variant in variants:
        if variant not in allowed:
            raise ValueError(f"unknown variant: {variant}")
    if not variants:
        raise ValueError("at least one variant is required")
    return variants


def discover_prompt(case_id: str, variant: str, prompts_dir: Path) -> Path:
    """Find the prompt file for a case and variant."""

    normalized_case = case_id.replace("_", "-")
    candidates = sorted(
        path
        for path in prompts_dir.glob("*.md")
        if path.name != "README.md" and path.name.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"))
    )
    for path in candidates:
        name = path.stem
        if variant in name and normalized_case in name:
            return path
    for path in candidates:
        if variant not in path.stem:
            continue
        text = path.read_text(encoding="utf-8")
        if case_id in text and f"Variant: `{variant}`" in text:
            return path
    raise FileNotFoundError(f"no {variant} prompt found for {case_id}")


def build_run_plan(
    cases: list[dict[str, Any]],
    variants: list[str],
    prompts_dir: Path,
    *,
    iterations: int,
    mode: str = "targeted",
    explicit_cases: bool = True,
    budget_profiles: dict[str, BudgetProfile] | None = None,
) -> list[PlannedRun]:
    """Create planned benchmark runs for selected cases and variants."""

    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if mode not in RUN_MODES:
        raise ValueError(f"unknown mode: {mode}")

    selected_cases = _select_mode_cases(cases, mode=mode, explicit_cases=explicit_cases)
    profiles = budget_profiles or DEFAULT_BUDGET_PROFILES
    mode_budget = profiles[mode]
    planned: list[PlannedRun] = []
    for iteration in range(1, iterations + 1):
        for case in selected_cases:
            budget = _effective_budget(case, mode_budget)
            for variant in variants:
                prompt_path = discover_prompt(case["id"], variant, prompts_dir)
                estimated_prompt_tokens = estimate_prompt_tokens(prompt_path.read_text(encoding="utf-8"))
                planned.append(
                    PlannedRun(
                        case_id=case["id"],
                        variant=variant,
                        iteration=iteration,
                        prompt_path=prompt_path,
                        category=case.get("category", "unknown"),
                        complexity=case.get("complexity"),
                        touchpoints=list(case.get("touchpoints", [])),
                        mode=mode,
                        budget=budget,
                        estimated_prompt_tokens=estimated_prompt_tokens,
                        projected_total_tokens=estimated_prompt_tokens + budget.max_completion_tokens,
                    )
                )
    return planned


def estimate_prompt_tokens(prompt_text: str) -> int:
    """Return a deterministic conservative approximation of prompt tokens."""

    if not prompt_text:
        return 0
    return max(1, (len(prompt_text) + 2) // 3)


def preflight_run_plan(
    planned_runs: list[PlannedRun],
    *,
    allow_large_token_run: bool = False,
) -> PreflightPlan:
    """Estimate planned token use before launching agents."""

    projected_suite_tokens = sum(planned.projected_total_tokens for planned in planned_runs)
    max_total_run_tokens = min(
        (planned.budget.max_total_run_tokens for planned in planned_runs),
        default=0,
    )
    suite_budget_obeyed = not planned_runs or projected_suite_tokens <= max_total_run_tokens
    items: list[PreflightItem] = []
    for planned in planned_runs:
        reason = _planned_budget_exception(planned)
        if reason and not allow_large_token_run:
            items.append(PreflightItem(planned=planned, status="skipped", reason=reason))
        elif reason:
            items.append(PreflightItem(planned=planned, status="warned", reason=reason))
        elif not suite_budget_obeyed and allow_large_token_run:
            items.append(
                PreflightItem(
                    planned=planned,
                    status="warned",
                    reason=(
                        f"projected suite token use {projected_suite_tokens} exceeds "
                        f"mode run budget {max_total_run_tokens}"
                    ),
                )
            )
        else:
            items.append(PreflightItem(planned=planned, status="allowed", reason="within budget"))
    return PreflightPlan(
        items=items,
        projected_suite_tokens=projected_suite_tokens,
        max_total_run_tokens=max_total_run_tokens,
        suite_budget_obeyed=suite_budget_obeyed,
    )


def format_preflight_plan(preflight: PreflightPlan) -> str:
    """Format a compact preflight plan for CLI output."""

    lines = [
        (
            "projected_suite_tokens="
            f"{preflight.projected_suite_tokens} max_total_run_tokens={preflight.max_total_run_tokens} "
            f"suite_budget_obeyed={'yes' if preflight.suite_budget_obeyed else 'no'}"
        )
    ]
    for item in preflight.items:
        planned = item.planned
        lines.append(
            " ".join(
                [
                    f"case={planned.case_id}",
                    f"variant={planned.variant}",
                    f"iteration={planned.iteration}",
                    f"mode={planned.mode}",
                    f"estimated_prompt_tokens={planned.estimated_prompt_tokens}",
                    f"max_total_tokens={planned.budget.max_total_tokens}",
                    f"projected_suite_tokens={preflight.projected_suite_tokens}",
                    f"status={item.status}",
                    f"reason={item.reason}",
                ]
            )
        )
    return "\n".join(lines)


def create_run_directory(results_dir: Path, *, timestamp: str | None = None) -> Path:
    """Create a timestamped run directory without overwriting prior output."""

    stamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = results_dir / stamp
    suffix = 1
    while candidate.exists():
        candidate = results_dir / f"{stamp}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def run_agent(agent_command: str, prompt_text: str, *, timeout_seconds: int) -> AgentExecution:
    """Run a configured agent command with prompt text on stdin."""

    command = split_command(agent_command)
    started = datetime.now()
    try:
        completed = subprocess.run(
            command,
            input=prompt_text,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        ended = datetime.now()
        return AgentExecution(
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            timed_out=False,
            started_at=started.isoformat(timespec="seconds"),
            ended_at=ended.isoformat(timespec="seconds"),
            duration_seconds=(ended - started).total_seconds(),
        )
    except subprocess.TimeoutExpired as error:
        ended = datetime.now()
        stdout = _decode_timeout_output(error.stdout)
        stderr = _decode_timeout_output(error.stderr)
        return AgentExecution(
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=None,
            timed_out=True,
            started_at=started.isoformat(timespec="seconds"),
            ended_at=ended.isoformat(timespec="seconds"),
            duration_seconds=(ended - started).total_seconds(),
        )


def run_planned_benchmark(
    planned: PlannedRun,
    *,
    agent_command: str,
    run_dir: Path,
    timeout_seconds: int,
    allow_large_token_run: bool = False,
    keep_full_artifacts: bool = False,
    agent_runner: Callable[[str, str], AgentExecution] | None = None,
) -> BenchmarkRunResult:
    """Run one planned benchmark and persist its artifacts."""

    prompt_text = planned.prompt_path.read_text(encoding="utf-8")
    planned_exception = _planned_budget_exception(planned)
    if planned_exception and not allow_large_token_run:
        execution = _skipped_execution(agent_command)
        parsed = ParsedBenchmarkResult(fields={}, block_text="")
        validation = ResultValidation(valid=False, errors=[planned_exception])
        token_metrics = TokenMetrics(
            estimated_prompt_tokens=planned.estimated_prompt_tokens,
            actual_input_tokens=None,
            actual_output_tokens=None,
            actual_total_tokens=None,
            token_budget_obeyed="no",
            token_budget_exception=planned_exception,
        )
        result = BenchmarkRunResult(
            planned=planned,
            artifact_dir=run_dir / planned.case_id / str(planned.iteration) / planned.variant,
            execution=execution,
            parsed=parsed,
            validation=validation,
            token_metrics=token_metrics,
        )
        write_run_artifacts(result, prompt_text, keep_full_artifacts=keep_full_artifacts)
        return result

    if agent_runner is None:
        execution = run_agent(agent_command, prompt_text, timeout_seconds=timeout_seconds)
    else:
        execution = agent_runner(agent_command, prompt_text)
    parsed = parse_benchmark_result(execution.stdout)
    validation = validate_result(parsed)
    errors = list(validation.errors)
    if execution.timed_out:
        errors.append("agent command timed out")
    elif execution.exit_code not in (0, None):
        errors.append(f"agent command exited with code {execution.exit_code}")
    token_metrics = _token_metrics(planned, execution)
    if token_metrics.token_budget_obeyed == "no" and token_metrics.token_budget_exception:
        errors.append(token_metrics.token_budget_exception)
    validation = ResultValidation(valid=not errors, errors=errors)
    result = BenchmarkRunResult(
        planned=planned,
        artifact_dir=run_dir / planned.case_id / str(planned.iteration) / planned.variant,
        execution=execution,
        parsed=parsed,
        validation=validation,
        token_metrics=token_metrics,
    )
    write_run_artifacts(result, prompt_text, keep_full_artifacts=keep_full_artifacts)
    return result


def run_benchmark_suite(
    planned_runs: list[PlannedRun],
    *,
    agent_command: str,
    run_dir: Path,
    timeout_seconds: int,
    apply_improvement_prompt: bool = False,
    improvement_prompt: Path | None = None,
    update_docker: bool = False,
    continue_on_docker_failure: bool = False,
    allow_large_token_run: bool = False,
    keep_full_artifacts: bool = False,
    agent_runner: Callable[..., AgentExecution] | None = None,
    docker_command_runner: Callable[[list[str], Path], AgentExecution] | None = None,
    repo_root: Path | None = None,
) -> list[BenchmarkRunResult]:
    """Run benchmark prompts, optional improvements, and optional Docker updates."""

    preflight = preflight_run_plan(planned_runs, allow_large_token_run=allow_large_token_run)
    if planned_runs and not preflight.suite_budget_obeyed and not allow_large_token_run:
        raise ValueError(
            f"projected suite token use {preflight.projected_suite_tokens} exceeds "
            f"mode run budget {preflight.max_total_run_tokens}; pass --allow-large-token-run to run anyway"
        )

    results: list[BenchmarkRunResult] = []
    iterations = sorted({planned.iteration for planned in planned_runs})
    for iteration in iterations:
        for planned in [item for item in planned_runs if item.iteration == iteration]:
            results.append(
                run_planned_benchmark(
                    planned,
                    agent_command=agent_command,
                    run_dir=run_dir,
                    timeout_seconds=timeout_seconds,
                    allow_large_token_run=allow_large_token_run,
                    keep_full_artifacts=keep_full_artifacts,
                    agent_runner=_wrap_agent_runner(agent_runner, timeout_seconds),
                )
            )
        if apply_improvement_prompt and improvement_prompt is not None and iteration != iterations[-1]:
            _run_improvement_prompt(
                improvement_prompt,
                agent_command=agent_command,
                run_dir=run_dir / "improvement" / str(iteration),
                timeout_seconds=timeout_seconds,
                agent_runner=agent_runner,
            )
            if update_docker:
                executions = run_docker_update(
                    repo_root or Path.cwd(),
                    command_runner=docker_command_runner,
                )
                if not continue_on_docker_failure and any(
                    execution.exit_code not in (0, None) for execution in executions
                ):
                    break
    return results


def write_run_artifacts(
    result: BenchmarkRunResult,
    prompt_text: str,
    *,
    keep_full_artifacts: bool = False,
) -> None:
    """Write raw and structured artifacts for a benchmark run."""

    artifact_dir = result.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if keep_full_artifacts:
        (artifact_dir / "prompt.md").write_text(prompt_text, encoding="utf-8")
        (artifact_dir / "stdout.txt").write_text(result.execution.stdout, encoding="utf-8")
        (artifact_dir / "stderr.txt").write_text(result.execution.stderr, encoding="utf-8")
    else:
        (artifact_dir / "stdout-tail.txt").write_text(
            _tail(result.execution.stdout, STDOUT_TAIL_CHARACTERS),
            encoding="utf-8",
        )
        (artifact_dir / "stderr-tail.txt").write_text(
            _tail(result.execution.stderr, STDERR_TAIL_CHARACTERS),
            encoding="utf-8",
        )
    (artifact_dir / "raw-result-block.txt").write_text(result.parsed.block_text, encoding="utf-8")
    (artifact_dir / "result.json").write_text(
        json.dumps(_result_to_dict(result), indent=2),
        encoding="utf-8",
    )


def run_docker_update(
    repo_root: Path,
    *,
    command_runner: Callable[[list[str], Path], AgentExecution] | None = None,
) -> list[AgentExecution]:
    """Run the Docker update command sequence."""

    commands = [
        ["docker", "compose", "build", "memory-mcp"],
        ["docker", "compose", "up", "-d", "postgres"],
        ["docker", "compose", "up", "-d", "memory-mcp"],
        ["docker", "compose", "ps"],
    ]
    executions = []
    for command in commands:
        if command_runner is None:
            executions.append(_run_command(command, cwd=repo_root))
        else:
            executions.append(command_runner(command, repo_root))
    return executions


def write_summary_json(results: list[BenchmarkRunResult], output_path: Path) -> None:
    """Write machine-readable run summary."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"runs": [_result_to_dict(result) for result in results]}, indent=2),
        encoding="utf-8",
    )


def write_summary_markdown(results: list[BenchmarkRunResult], output_path: Path) -> None:
    """Write human-readable run summary."""

    lines = [
        "# Outline Benchmark Run Summary",
        "",
        "| Case | Iteration | Variant | Status | Estimated Prompt Tokens | Actual Total Tokens | Token Budget Obeyed | Source Read Budget Obeyed | Result Artifact Path |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        fields = result.parsed.fields
        actual_total = _unknown_if_none(result.token_metrics.actual_total_tokens)
        lines.append(
            "| "
            + " | ".join(
                [
                    result.planned.case_id,
                    str(result.planned.iteration),
                    result.planned.variant,
                    "yes" if result.validation.valid else "no",
                    str(result.token_metrics.estimated_prompt_tokens),
                    str(actual_total),
                    result.token_metrics.token_budget_obeyed,
                    fields.get("source_read_budget_obeyed", "unknown"),
                    str(result.artifact_dir),
                ]
            )
            + " |"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _result_to_dict(result: BenchmarkRunResult) -> dict[str, Any]:
    return {
        "case_id": result.planned.case_id,
        "iteration": result.planned.iteration,
        "variant": result.planned.variant,
        "category": result.planned.category,
        "complexity": result.planned.complexity,
        "touchpoints": result.planned.touchpoints,
        "prompt_path": str(result.planned.prompt_path),
        "artifact_dir": str(result.artifact_dir),
        "command": result.execution.command,
        "exit_code": result.execution.exit_code,
        "timed_out": result.execution.timed_out,
        "started_at": result.execution.started_at,
        "ended_at": result.execution.ended_at,
        "duration_seconds": result.execution.duration_seconds,
        "valid": result.validation.valid,
        "errors": result.validation.errors,
        "estimated_prompt_tokens": result.token_metrics.estimated_prompt_tokens,
        "actual_input_tokens": _unknown_if_none(result.token_metrics.actual_input_tokens),
        "actual_output_tokens": _unknown_if_none(result.token_metrics.actual_output_tokens),
        "actual_total_tokens": _unknown_if_none(result.token_metrics.actual_total_tokens),
        "token_budget_obeyed": result.token_metrics.token_budget_obeyed,
        "token_budget_exception": result.token_metrics.token_budget_exception,
        "source_read_budget_obeyed": result.parsed.fields.get("source_read_budget_obeyed", "unknown"),
        "budget": {
            "mode": result.planned.mode,
            "max_prompt_tokens": result.planned.budget.max_prompt_tokens,
            "max_completion_tokens": result.planned.budget.max_completion_tokens,
            "max_total_tokens": result.planned.budget.max_total_tokens,
            "max_total_run_tokens": result.planned.budget.max_total_run_tokens,
            "max_source_files_before_edit": result.planned.budget.max_source_files_before_edit,
            "max_snippets_before_edit": result.planned.budget.max_snippets_before_edit,
        },
        "parsed": result.parsed.fields,
    }


def _select_mode_cases(
    cases: list[dict[str, Any]],
    *,
    mode: str,
    explicit_cases: bool,
) -> list[dict[str, Any]]:
    if mode != "smoke" or explicit_cases or len(cases) <= 1:
        return cases
    return cases[:1]


def _effective_budget(case: dict[str, Any], default_budget: BudgetProfile) -> BudgetProfile:
    overrides = case.get("budget_overrides") or {}
    if not overrides:
        return default_budget
    allowed = set(BudgetProfile.__dataclass_fields__)
    invalid = set(overrides) - allowed
    if invalid:
        raise ValueError("unknown budget override: " + ", ".join(sorted(invalid)))
    return default_budget.replace(**{key: int(value) for key, value in overrides.items()})


def _planned_budget_exception(planned: PlannedRun) -> str:
    if planned.estimated_prompt_tokens > planned.budget.max_prompt_tokens:
        return (
            f"estimated prompt tokens {planned.estimated_prompt_tokens} exceed "
            f"max_prompt_tokens {planned.budget.max_prompt_tokens}"
        )
    if planned.projected_total_tokens > planned.budget.max_total_tokens:
        return (
            f"projected total tokens {planned.projected_total_tokens} exceed "
            f"max_total_tokens {planned.budget.max_total_tokens}"
        )
    return ""


def _token_metrics(planned: PlannedRun, execution: AgentExecution) -> TokenMetrics:
    actual_input, actual_output, actual_total = parse_actual_token_usage(execution.stdout + "\n" + execution.stderr)
    planned_exception = _planned_budget_exception(planned)
    if planned_exception:
        return TokenMetrics(
            estimated_prompt_tokens=planned.estimated_prompt_tokens,
            actual_input_tokens=actual_input,
            actual_output_tokens=actual_output,
            actual_total_tokens=actual_total,
            token_budget_obeyed="no",
            token_budget_exception=planned_exception,
        )
    if actual_total is None:
        return TokenMetrics(
            estimated_prompt_tokens=planned.estimated_prompt_tokens,
            actual_input_tokens=actual_input,
            actual_output_tokens=actual_output,
            actual_total_tokens=actual_total,
            token_budget_obeyed="unknown",
            token_budget_exception="",
        )
    if actual_total > planned.budget.max_total_tokens:
        return TokenMetrics(
            estimated_prompt_tokens=planned.estimated_prompt_tokens,
            actual_input_tokens=actual_input,
            actual_output_tokens=actual_output,
            actual_total_tokens=actual_total,
            token_budget_obeyed="no",
            token_budget_exception=(
                f"actual total tokens exceeded max_total_tokens: "
                f"{actual_total} > {planned.budget.max_total_tokens}"
            ),
        )
    return TokenMetrics(
        estimated_prompt_tokens=planned.estimated_prompt_tokens,
        actual_input_tokens=actual_input,
        actual_output_tokens=actual_output,
        actual_total_tokens=actual_total,
        token_budget_obeyed="yes",
        token_budget_exception="",
    )


def parse_actual_token_usage(output: str) -> tuple[int | None, int | None, int | None]:
    """Parse provider-neutral token usage fields when wrappers print them."""

    actual_input = _first_token_value(output, ("actual_input_tokens", "input_tokens", "prompt_tokens"))
    actual_output = _first_token_value(
        output,
        ("actual_output_tokens", "output_tokens", "completion_tokens"),
    )
    actual_total = _first_token_value(output, ("actual_total_tokens", "total_tokens"))
    if actual_total is None and actual_input is not None and actual_output is not None:
        actual_total = actual_input + actual_output
    return actual_input, actual_output, actual_total


def _first_token_value(output: str, keys: tuple[str, ...]) -> int | None:
    for key in keys:
        match = re.search(rf"\b{re.escape(key)}\b\s*[:=]\s*(\d+)", output)
        if match:
            return int(match.group(1))
    return None


def _skipped_execution(agent_command: str) -> AgentExecution:
    now = datetime.now().isoformat(timespec="seconds")
    return AgentExecution(
        command=split_command(agent_command),
        stdout="",
        stderr="",
        exit_code=None,
        timed_out=False,
        started_at=now,
        ended_at=now,
        duration_seconds=0.0,
    )


def _tail(text: str, characters: int) -> str:
    if len(text) <= characters:
        return text
    return text[-characters:]


def _unknown_if_none(value: int | None) -> int | str:
    return "unknown" if value is None else value


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def _run_command(command: list[str], *, cwd: Path) -> AgentExecution:
    started = datetime.now()
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    ended = datetime.now()
    return AgentExecution(
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
        timed_out=False,
        started_at=started.isoformat(timespec="seconds"),
        ended_at=ended.isoformat(timespec="seconds"),
        duration_seconds=(ended - started).total_seconds(),
    )


def _run_improvement_prompt(
    prompt_path: Path,
    *,
    agent_command: str,
    run_dir: Path,
    timeout_seconds: int,
    agent_runner: Callable[..., AgentExecution] | None,
) -> AgentExecution:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    if agent_runner is None:
        execution = run_agent(agent_command, prompt_text, timeout_seconds=timeout_seconds)
    else:
        execution = agent_runner(agent_command, prompt_text, timeout_seconds=timeout_seconds)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.md").write_text(prompt_text, encoding="utf-8")
    (run_dir / "stdout.txt").write_text(execution.stdout, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(execution.stderr, encoding="utf-8")
    (run_dir / "result.json").write_text(
        json.dumps(
            {
                "command": execution.command,
                "exit_code": execution.exit_code,
                "timed_out": execution.timed_out,
                "started_at": execution.started_at,
                "ended_at": execution.ended_at,
                "duration_seconds": execution.duration_seconds,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return execution


def _wrap_agent_runner(
    agent_runner: Callable[..., AgentExecution] | None,
    timeout_seconds: int,
) -> Callable[[str, str], AgentExecution] | None:
    if agent_runner is None:
        return None

    def wrapped(agent_command: str, prompt_text: str) -> AgentExecution:
        return agent_runner(agent_command, prompt_text, timeout_seconds=timeout_seconds)

    return wrapped


def split_command(command: str) -> list[str]:
    """Split a command string using Windows rules when applicable."""

    if os.name != "nt":
        return shlex.split(command)

    shell32 = ctypes.windll.shell32
    kernel32 = ctypes.windll.kernel32
    shell32.CommandLineToArgvW.argtypes = [c_wchar_p, POINTER(c_int)]
    shell32.CommandLineToArgvW.restype = POINTER(c_wchar_p)
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    argc = c_int()
    argv = shell32.CommandLineToArgvW(command, byref(argc))
    if not argv:
        raise ValueError(f"could not parse command: {command}")
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        kernel32.LocalFree(argv)
