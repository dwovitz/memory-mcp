"""Tests for the Outline benchmark runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from benchmarks.outline_benchmark_runner import (
    AgentExecution,
    DEFAULT_BUDGET_PROFILES,
    ParsedBenchmarkResult,
    build_run_plan,
    create_run_directory,
    discover_prompt,
    format_preflight_plan,
    load_cases,
    parse_benchmark_result,
    preflight_run_plan,
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
    assert plan[0].mode == "targeted"
    assert plan[0].budget.max_total_tokens == DEFAULT_BUDGET_PROFILES["targeted"].max_total_tokens
    assert plan[0].estimated_prompt_tokens > 0


def test_smoke_mode_reduces_plan_when_cases_are_not_explicit(tmp_path: Path) -> None:
    cases = []
    for index in range(1, 4):
        case_id = f"outline_case_{index}"
        prompt = tmp_path / f"0{index}a-baseline-outline-case-{index}.md"
        prompt.write_text(f"Prompt {index}", encoding="utf-8")
        cases.append({"id": case_id, "category": "feature_update"})

    plan = build_run_plan(
        cases,
        ["baseline"],
        tmp_path,
        iterations=1,
        mode="smoke",
        explicit_cases=False,
    )

    assert [planned.case_id for planned in plan] == ["outline_case_1"]


def test_preflight_reports_estimated_tokens_without_launching_agent(tmp_path: Path) -> None:
    prompt = tmp_path / "01a-baseline-outline-feature.md"
    prompt.write_text("Prompt body", encoding="utf-8")
    planned = build_run_plan(
        [{"id": "outline_feature", "category": "feature_update"}],
        ["baseline"],
        tmp_path,
        iterations=1,
        mode="targeted",
    )

    preflight = preflight_run_plan(planned)
    output = format_preflight_plan(preflight)

    assert preflight.projected_suite_tokens > 0
    assert preflight.items[0].status == "allowed"
    assert "case=outline_feature" in output
    assert "estimated_prompt_tokens=" in output
    assert "mode=targeted" in output


def test_suite_budget_overflow_fails_before_launch_unless_allowed(tmp_path: Path) -> None:
    prompt = tmp_path / "01a-baseline-outline-feature.md"
    prompt.write_text("Prompt body", encoding="utf-8")
    tiny_budget = DEFAULT_BUDGET_PROFILES["targeted"].replace(max_total_run_tokens=1)
    planned = build_run_plan(
        [{"id": "outline_feature", "category": "feature_update"}],
        ["baseline"],
        tmp_path,
        iterations=1,
        budget_profiles={"targeted": tiny_budget},
    )
    launched = False

    def fake_agent(agent_command: str, prompt_text: str, *, timeout_seconds: int) -> AgentExecution:
        nonlocal launched
        launched = True
        raise AssertionError("agent should not launch")

    try:
        run_benchmark_suite(
            planned,
            agent_command="fake-agent",
            run_dir=tmp_path / "run",
            timeout_seconds=10,
            agent_runner=fake_agent,
        )
    except ValueError as error:
        assert "projected suite token use" in str(error)
    else:
        raise AssertionError("expected suite budget overflow to raise")
    assert launched is False

    results = run_benchmark_suite(
        planned,
        agent_command="fake-agent",
        run_dir=tmp_path / "run-allowed",
        timeout_seconds=10,
        allow_large_token_run=True,
        agent_runner=lambda *args, **kwargs: AgentExecution(
            command=["fake-agent"],
            stdout="BENCHMARK_RESULT",
            stderr="",
            exit_code=0,
            timed_out=False,
            started_at="2026-04-30T12:00:00",
            ended_at="2026-04-30T12:00:01",
            duration_seconds=1.0,
        ),
    )

    assert len(results) == 1


def test_create_run_directory_avoids_existing_timestamp(tmp_path: Path) -> None:
    existing = tmp_path / "20260430-120000"
    existing.mkdir()

    run_dir = create_run_directory(tmp_path, timestamp="20260430-120000")

    assert run_dir.name == "20260430-120000-1"
    assert run_dir.is_dir()


def test_run_planned_benchmark_saves_compact_agent_artifacts_by_default(tmp_path: Path) -> None:
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
    assert not (artifact_dir / "prompt.md").exists()
    assert not (artifact_dir / "stdout.txt").exists()
    assert not (artifact_dir / "stderr.txt").exists()
    assert "saw prompt: Prompt body" in (artifact_dir / "stdout-tail.txt").read_text(encoding="utf-8")
    assert (artifact_dir / "stderr-tail.txt").read_text(encoding="utf-8") == ""
    assert (artifact_dir / "raw-result-block.txt").read_text(encoding="utf-8").startswith("BENCHMARK_RESULT")
    saved = json.loads((artifact_dir / "result.json").read_text(encoding="utf-8"))
    assert saved["parsed"]["case_id"] == "outline_feature"
    assert saved["valid"] is True
    assert saved["estimated_prompt_tokens"] == result.token_metrics.estimated_prompt_tokens


def test_keep_full_artifacts_preserves_prompt_and_transcripts(tmp_path: Path) -> None:
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
        keep_full_artifacts=True,
    )

    artifact_dir = tmp_path / "run" / "outline_feature" / "1" / "baseline"
    assert (artifact_dir / "prompt.md").read_text(encoding="utf-8") == "Prompt body"
    assert (artifact_dir / "stdout.txt").read_text(encoding="utf-8") == result.execution.stdout
    assert (artifact_dir / "stderr.txt").read_text(encoding="utf-8") == result.execution.stderr


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
    assert summary["runs"][0]["estimated_prompt_tokens"] == result.token_metrics.estimated_prompt_tokens
    assert summary["runs"][0]["actual_total_tokens"] == "unknown"
    assert summary["runs"][0]["token_budget_obeyed"] == "unknown"
    assert "| outline_feature | 1 | baseline | no |" in (
        tmp_path / "summary.md"
    ).read_text(encoding="utf-8")


def test_actual_token_usage_is_parsed_and_budget_failure_is_reported(tmp_path: Path) -> None:
    prompt = tmp_path / "01a-baseline-outline-feature.md"
    prompt.write_text("Prompt body", encoding="utf-8")
    tiny_budget = DEFAULT_BUDGET_PROFILES["targeted"].replace(
        max_completion_tokens=1,
        max_total_tokens=15,
    )
    planned = build_run_plan(
        [{"id": "outline_feature", "category": "feature_update"}],
        ["baseline"],
        tmp_path,
        iterations=1,
        budget_profiles={"targeted": tiny_budget},
    )[0]

    result = run_planned_benchmark(
        planned,
        agent_command="fake-agent",
        run_dir=tmp_path / "run",
        timeout_seconds=10,
        allow_large_token_run=True,
        agent_runner=lambda *args, **kwargs: AgentExecution(
            command=["fake-agent"],
            stdout=(
                "usage: input_tokens=7 output_tokens=9 total_tokens=16\n"
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
        ),
    )

    assert result.token_metrics.actual_input_tokens == 7
    assert result.token_metrics.actual_output_tokens == 9
    assert result.token_metrics.actual_total_tokens == 16
    assert result.token_metrics.token_budget_obeyed == "no"
    assert "actual total tokens exceeded" in result.token_metrics.token_budget_exception


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
