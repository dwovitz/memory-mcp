"""Run local benchmark checks and write timestamped artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "benchmarks" / "results" / "terminal-runs"


@dataclass(frozen=True)
class BenchmarkCommand:
    """One terminal command included in the benchmark suite."""

    name: str
    command: list[str]


@dataclass(frozen=True)
class BenchmarkCommandResult:
    """Captured result for one benchmark command."""

    name: str
    command: list[str]
    returncode: int
    duration_seconds: float
    stdout_path: Path
    stderr_path: Path

    @property
    def passed(self) -> bool:
        return self.returncode == 0


def default_benchmark_commands() -> list[BenchmarkCommand]:
    """Return all local benchmark commands run by default."""

    return [
        BenchmarkCommand(
            name="benchmark-pytest-suite",
            command=[
                sys.executable,
                "-m",
                "pytest",
                "tests/test_benchmark_cases.py",
                "tests/test_outline_benchmark_runner.py",
                "tests/test_run_outline_benchmarks_cli.py",
                "--durations=10",
            ],
        ),
        BenchmarkCommand(
            name="outline-runner-smoke-preflight",
            command=[
                sys.executable,
                "benchmarks/run_outline_benchmarks.py",
                "--agent-profile",
                "codex",
                "--mode",
                "smoke",
                "--dry-run",
                "--allow-large-token-run",
            ],
        ),
    ]


def create_timestamped_output_dir(output_root: Path, *, timestamp: str | None = None) -> Path:
    """Create a date/time output directory for a benchmark run."""

    stamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    date_part, time_part = stamp.split("-", maxsplit=1)
    candidate = output_root / date_part[:4] / date_part[4:6] / date_part[6:8] / time_part
    suffix = 1
    while candidate.exists():
        candidate = output_root / date_part[:4] / date_part[4:6] / date_part[6:8] / f"{time_part}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def run_benchmark_commands(
    commands: Sequence[BenchmarkCommand],
    *,
    output_dir: Path,
    cwd: Path,
    timeout_seconds: int = 1800,
) -> list[BenchmarkCommandResult]:
    """Run each benchmark command and capture stdout/stderr artifacts."""

    results: list[BenchmarkCommandResult] = []
    for benchmark in commands:
        command_dir = output_dir / benchmark.name
        command_dir.mkdir(parents=True, exist_ok=True)
        started = datetime.now()
        completed = subprocess.run(
            benchmark.command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        ended = datetime.now()
        stdout_path = command_dir / "stdout.txt"
        stderr_path = command_dir / "stderr.txt"
        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        (command_dir / "command.json").write_text(
            json.dumps(
                {
                    "name": benchmark.name,
                    "command": benchmark.command,
                    "returncode": completed.returncode,
                    "started_at": started.isoformat(timespec="seconds"),
                    "ended_at": ended.isoformat(timespec="seconds"),
                    "duration_seconds": (ended - started).total_seconds(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        results.append(
            BenchmarkCommandResult(
                name=benchmark.name,
                command=benchmark.command,
                returncode=completed.returncode,
                duration_seconds=(ended - started).total_seconds(),
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
        )
    return results


def build_codex_review_prompt(output_dir: Path) -> str:
    """Build a paste-ready prompt for reviewing benchmark output in Codex."""

    return "\n".join(
        [
            "Review the benchmark results for memory-mcp.",
            "",
            f"Run directory: {output_dir}",
            f"Human summary: {output_dir / 'summary.md'}",
            f"Machine summary: {output_dir / 'summary.json'}",
            "",
            "Please inspect the summaries and command artifacts, prioritize regressions,",
            "identify suspicious timing or budget changes, and recommend the next concrete",
            "code or benchmark changes. Keep findings grounded in file paths and command",
            "output from this run.",
            "",
        ]
    )


def write_benchmark_report(
    results: Sequence[BenchmarkCommandResult],
    *,
    output_dir: Path,
    started_at: str,
) -> None:
    """Write JSON, Markdown, and Codex review prompt artifacts."""

    passed = all(result.passed for result in results)
    summary = {
        "started_at": started_at,
        "output_dir": str(output_dir),
        "passed": passed,
        "commands": [
            {
                "name": result.name,
                "command": result.command,
                "returncode": result.returncode,
                "passed": result.passed,
                "duration_seconds": result.duration_seconds,
                "stdout_path": str(result.stdout_path),
                "stderr_path": str(result.stderr_path),
            }
            for result in results
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    lines = [
        "# memory-mcp Terminal Benchmark Summary",
        "",
        f"Started: {started_at}",
        f"Output: {output_dir}",
        f"Overall: {'pass' if passed else 'fail'}",
        "",
        "| Command | Status | Duration Seconds | Return Code | Stdout | Stderr |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    result.name,
                    "pass" if result.passed else "fail",
                    f"{result.duration_seconds:.3f}",
                    str(result.returncode),
                    str(result.stdout_path),
                    str(result.stderr_path),
                ]
            )
            + " |"
        )
    (output_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output_dir / "codex-review-prompt.md").write_text(
        build_codex_review_prompt(output_dir),
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all local memory-mcp benchmarks.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args(argv)

    started = datetime.now().isoformat(timespec="seconds")
    output_dir = create_timestamped_output_dir(args.output_root)
    results = run_benchmark_commands(
        default_benchmark_commands(),
        output_dir=output_dir,
        cwd=REPO_ROOT,
        timeout_seconds=args.timeout_seconds,
    )
    write_benchmark_report(results, output_dir=output_dir, started_at=started)

    prompt_path = output_dir / "codex-review-prompt.md"
    print(f"Benchmark output: {output_dir}")
    print(f"Summary: {output_dir / 'summary.md'}")
    print(f"Codex review prompt: {prompt_path}")
    print("")
    print(prompt_path.read_text(encoding="utf-8"))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
