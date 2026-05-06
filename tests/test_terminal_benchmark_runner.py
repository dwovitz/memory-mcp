"""Tests for the terminal benchmark runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from benchmarks.run_all_benchmarks import (
    BenchmarkCommand,
    build_codex_review_prompt,
    create_timestamped_output_dir,
    default_benchmark_commands,
    run_benchmark_commands,
    write_benchmark_report,
)


def test_create_timestamped_output_dir_uses_date_time_tree(tmp_path: Path) -> None:
    existing = tmp_path / "2026" / "05" / "05" / "143000"
    existing.mkdir(parents=True)

    output_dir = create_timestamped_output_dir(tmp_path, timestamp="20260505-143000")

    assert output_dir == tmp_path / "2026" / "05" / "05" / "143000-1"
    assert output_dir.is_dir()


def test_default_benchmark_commands_use_codex_profile_preflight() -> None:
    commands = {command.name: command.command for command in default_benchmark_commands()}

    assert "tests/test_run_outline_benchmarks_cli.py" in commands["benchmark-pytest-suite"]
    assert "--agent-profile" in commands["outline-runner-smoke-preflight"]
    assert "codex" in commands["outline-runner-smoke-preflight"]
    assert "--agent-command" not in commands["outline-runner-smoke-preflight"]


def test_run_benchmark_commands_captures_artifacts(tmp_path: Path) -> None:
    command = BenchmarkCommand(
        name="sample",
        command=[
            sys.executable,
            "-c",
            "import sys; print('benchmark ok'); print('benchmark err', file=sys.stderr)",
        ],
    )

    results = run_benchmark_commands([command], output_dir=tmp_path, cwd=tmp_path)

    assert len(results) == 1
    assert results[0].name == "sample"
    assert results[0].passed is True
    assert (tmp_path / "sample" / "stdout.txt").read_text(encoding="utf-8") == "benchmark ok\n"
    assert (tmp_path / "sample" / "stderr.txt").read_text(encoding="utf-8") == "benchmark err\n"


def test_write_benchmark_report_includes_review_prompt(tmp_path: Path) -> None:
    command = BenchmarkCommand(
        name="sample",
        command=[sys.executable, "-c", "print('ok')"],
    )
    results = run_benchmark_commands([command], output_dir=tmp_path, cwd=tmp_path)

    write_benchmark_report(results, output_dir=tmp_path, started_at="2026-05-05T14:30:00")

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["started_at"] == "2026-05-05T14:30:00"
    assert summary["passed"] is True
    assert summary["commands"][0]["name"] == "sample"
    assert "| sample | pass |" in (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Review the benchmark results" in (
        tmp_path / "codex-review-prompt.md"
    ).read_text(encoding="utf-8")


def test_build_codex_review_prompt_points_at_summary_files(tmp_path: Path) -> None:
    prompt = build_codex_review_prompt(tmp_path)

    assert str(tmp_path / "summary.md") in prompt
    assert str(tmp_path / "summary.json") in prompt
    assert "prioritize regressions" in prompt
