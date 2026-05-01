"""Automated runner utilities for Outline memory benchmarks."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import ctypes
from ctypes import POINTER, byref, c_int, c_wchar_p
from ctypes import wintypes
from dataclasses import dataclass
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
) -> list[PlannedRun]:
    """Create planned benchmark runs for selected cases and variants."""

    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    planned: list[PlannedRun] = []
    for iteration in range(1, iterations + 1):
        for case in cases:
            for variant in variants:
                planned.append(
                    PlannedRun(
                        case_id=case["id"],
                        variant=variant,
                        iteration=iteration,
                        prompt_path=discover_prompt(case["id"], variant, prompts_dir),
                        category=case.get("category", "unknown"),
                        complexity=case.get("complexity"),
                        touchpoints=list(case.get("touchpoints", [])),
                    )
                )
    return planned


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
    agent_runner: Callable[[str, str], AgentExecution] | None = None,
) -> BenchmarkRunResult:
    """Run one planned benchmark and persist its artifacts."""

    prompt_text = planned.prompt_path.read_text(encoding="utf-8")
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
    validation = ResultValidation(valid=not errors, errors=errors)
    result = BenchmarkRunResult(
        planned=planned,
        artifact_dir=run_dir / planned.case_id / str(planned.iteration) / planned.variant,
        execution=execution,
        parsed=parsed,
        validation=validation,
    )
    write_run_artifacts(result, prompt_text)
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
    agent_runner: Callable[..., AgentExecution] | None = None,
    docker_command_runner: Callable[[list[str], Path], AgentExecution] | None = None,
    repo_root: Path | None = None,
) -> list[BenchmarkRunResult]:
    """Run benchmark prompts, optional improvements, and optional Docker updates."""

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


def write_run_artifacts(result: BenchmarkRunResult, prompt_text: str) -> None:
    """Write raw and structured artifacts for a benchmark run."""

    artifact_dir = result.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "prompt.md").write_text(prompt_text, encoding="utf-8")
    (artifact_dir / "stdout.txt").write_text(result.execution.stdout, encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text(result.execution.stderr, encoding="utf-8")
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
        "| Case | Iteration | Variant | Category | Complexity | Valid | Outcome |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        fields = result.parsed.fields
        lines.append(
            "| "
            + " | ".join(
                [
                    result.planned.case_id,
                    str(result.planned.iteration),
                    result.planned.variant,
                    result.planned.category,
                    result.planned.complexity or "",
                    "yes" if result.validation.valid else "no",
                    fields.get("outcome", ""),
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
        "parsed": result.parsed.fields,
    }


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
