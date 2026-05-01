"""Tests for the Outline benchmark runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from benchmarks.outline_benchmark_runner import (
    AgentExecution,
    ParsedBenchmarkResult,
    build_run_plan,
    create_run_directory,
    discover_prompt,
    load_cases,
    parse_benchmark_result,
    run_agent,
    run_benchmark_suite,
    run_docker_update,
    run_planned_benchmark,
    select_cases,
    select_variants,
    validate_result,
    write_summary_json,
    write_summary_markdown,
)


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


def test_load_and_select_cases(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {"id": "case_a", "category": "bug_fix"},
                {"id": "case_b", "category": "feature_update"},
            ]
        ),
        encoding="utf-8",
    )

    cases = load_cases(cases_path)
    selected = select_cases(cases, ["case_b"])

    assert [case["id"] for case in cases] == ["case_a", "case_b"]
    assert [case["id"] for case in selected] == ["case_b"]


def test_select_variants_rejects_unknown_variant() -> None:
    assert select_variants("baseline,memory") == ["baseline", "memory"]

    try:
        select_variants("baseline,experimental")
    except ValueError as error:
        assert "unknown variant: experimental" in str(error)
    else:
        raise AssertionError("expected invalid variant to raise")


def test_discover_prompt_finds_case_variant_file(tmp_path: Path) -> None:
    prompt = tmp_path / "01a-baseline-outline-feature.md"
    prompt.write_text("case_id", encoding="utf-8")

    assert discover_prompt("outline_feature", "baseline", tmp_path) == prompt


def test_build_run_plan_includes_case_metadata(tmp_path: Path) -> None:
    prompt = tmp_path / "01b-memory-outline-feature.md"
    prompt.write_text("prompt", encoding="utf-8")
    cases = [
        {
            "id": "outline_feature",
            "category": "feature_update",
            "complexity": "complex",
            "touchpoints": ["api", "authorization", "tests"],
        }
    ]

    plan = build_run_plan(cases, ["memory"], tmp_path, iterations=2)

    assert len(plan) == 2
    assert plan[0].case_id == "outline_feature"
    assert plan[0].variant == "memory"
    assert plan[0].iteration == 1
    assert plan[0].category == "feature_update"
    assert plan[0].complexity == "complex"


def test_create_run_directory_avoids_existing_timestamp(tmp_path: Path) -> None:
    existing = tmp_path / "20260430-120000"
    existing.mkdir()

    run_dir = create_run_directory(tmp_path, timestamp="20260430-120000")

    assert run_dir.name == "20260430-120000-1"
    assert run_dir.is_dir()


def test_run_planned_benchmark_saves_agent_artifacts(tmp_path: Path) -> None:
    prompt = tmp_path / "01a-baseline-outline-feature.md"
    prompt.write_text("Prompt body", encoding="utf-8")
    agent = tmp_path / "fake_agent.py"
    agent.write_text(
        """
import sys
prompt = sys.stdin.read()
print("saw prompt:", prompt)
print("```text")
print("BENCHMARK_RESULT")
print("case_id: outline_feature")
print("project: outline")
print("variant: baseline")
print("worktree: D:\\\\git\\\\ai\\\\outline-benchmarks\\\\case\\\\baseline")
print("branch: benchmark/case-baseline")
print("memory_used: no")
print("files_changed: server/routes/api.ts")
print("tests_run: yarn test server/routes/api.test.ts")
print("outcome: completed")
print("```")
""",
        encoding="utf-8",
    )
    planned = build_run_plan(
        [{"id": "outline_feature", "category": "feature_update", "complexity": "complex"}],
        ["baseline"],
        tmp_path,
        iterations=1,
    )[0]

    result = run_planned_benchmark(
        planned,
        agent_command=f"{sys.executable} {agent}",
        run_dir=tmp_path / "run",
        timeout_seconds=10,
    )

    artifact_dir = tmp_path / "run" / "outline_feature" / "1" / "baseline"
    assert result.validation.valid is True
    assert (artifact_dir / "prompt.md").read_text(encoding="utf-8") == "Prompt body"
    assert "saw prompt: Prompt body" in (artifact_dir / "stdout.txt").read_text(encoding="utf-8")
    assert (artifact_dir / "stderr.txt").read_text(encoding="utf-8") == ""
    assert (artifact_dir / "raw-result-block.txt").read_text(encoding="utf-8").startswith("BENCHMARK_RESULT")
    saved = json.loads((artifact_dir / "result.json").read_text(encoding="utf-8"))
    assert saved["parsed"]["case_id"] == "outline_feature"
    assert saved["valid"] is True


def test_run_agent_replaces_undecodable_output_bytes() -> None:
    agent_command = (
        f"{sys.executable} -c "
        "\"import sys; sys.stdout.buffer.write(bytes([98,101,102,111,114,101,157,97,102,116,101,114]))\""
    )

    execution = run_agent(agent_command, "Prompt body", timeout_seconds=10)

    assert execution.exit_code == 0
    assert execution.stdout == "before\ufffdafter"
    assert execution.stderr == ""


def test_summary_writers_include_category_and_validity(tmp_path: Path) -> None:
    prompt = tmp_path / "01a-baseline-outline-feature.md"
    prompt.write_text("Prompt body", encoding="utf-8")
    planned = build_run_plan(
        [{"id": "outline_feature", "category": "feature_update", "complexity": "complex"}],
        ["baseline"],
        tmp_path,
        iterations=1,
    )[0]
    result = run_planned_benchmark(
        planned,
        agent_command=f"{sys.executable} -c \"print('BENCHMARK_RESULT')\"",
        run_dir=tmp_path / "run",
        timeout_seconds=10,
    )

    write_summary_json([result], tmp_path / "summary.json")
    write_summary_markdown([result], tmp_path / "summary.md")

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["runs"][0]["category"] == "feature_update"
    assert summary["runs"][0]["complexity"] == "complex"
    assert "| outline_feature | 1 | baseline | feature_update | complex | no |" in (
        tmp_path / "summary.md"
    ).read_text(encoding="utf-8")


def test_run_docker_update_uses_expected_command_order(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_runner(command: list[str], cwd: Path) -> AgentExecution:
        calls.append(command)
        return AgentExecution(
            command=command,
            stdout="ok",
            stderr="",
            exit_code=0,
            timed_out=False,
            started_at="2026-04-30T12:00:00",
            ended_at="2026-04-30T12:00:01",
            duration_seconds=1.0,
        )

    executions = run_docker_update(tmp_path, command_runner=fake_runner)

    assert [execution.command for execution in executions] == [
        ["docker", "compose", "build", "memory-mcp"],
        ["docker", "compose", "up", "-d", "postgres"],
        ["docker", "compose", "up", "-d", "memory-mcp"],
        ["docker", "compose", "ps"],
    ]
    assert calls == [execution.command for execution in executions]


def test_run_benchmark_suite_runs_improvement_prompt_between_iterations(tmp_path: Path) -> None:
    prompt = tmp_path / "01a-baseline-outline-feature.md"
    prompt.write_text("Prompt body", encoding="utf-8")
    improvement_prompt = tmp_path / "04-memory-mcp-improvement.md"
    improvement_prompt.write_text("Improve memory-mcp", encoding="utf-8")
    planned = build_run_plan(
        [{"id": "outline_feature", "category": "feature_update", "complexity": "complex"}],
        ["baseline"],
        tmp_path,
        iterations=2,
    )
    seen_prompts: list[str] = []

    def fake_agent(agent_command: str, prompt_text: str, *, timeout_seconds: int) -> AgentExecution:
        seen_prompts.append(prompt_text)
        return AgentExecution(
            command=[agent_command],
            stdout=(
                "BENCHMARK_RESULT\n"
                "case_id: outline_feature\n"
                "project: outline\n"
                "variant: baseline\n"
                "worktree: D:\\git\\ai\\outline-benchmarks\\case\\baseline\n"
                "branch: benchmark/case-baseline\n"
                "memory_used: no\n"
                "files_changed: server/routes/api.ts\n"
                "tests_run: yarn test server/routes/api.test.ts\n"
                "outcome: completed\n"
            ),
            stderr="",
            exit_code=0,
            timed_out=False,
            started_at="2026-04-30T12:00:00",
            ended_at="2026-04-30T12:00:01",
            duration_seconds=1.0,
        )

    results = run_benchmark_suite(
        planned,
        agent_command="fake-agent",
        run_dir=tmp_path / "run",
        timeout_seconds=10,
        apply_improvement_prompt=True,
        improvement_prompt=improvement_prompt,
        agent_runner=fake_agent,
    )

    assert len(results) == 2
    assert seen_prompts == ["Prompt body", "Improve memory-mcp", "Prompt body"]
    assert (tmp_path / "run" / "improvement" / "1" / "stdout.txt").exists()
