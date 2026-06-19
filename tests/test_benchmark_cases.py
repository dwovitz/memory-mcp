"""Product benchmark tests for task-oriented context packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from memory_mcp.models import Memory
from memory_mcp.retrieval import MemorySearchResult
from memory_mcp.services import ContextSynthesisService


BENCHMARK_CASES = Path(__file__).resolve().parents[1] / "benchmarks" / "cases.json"
BENCHMARK_PROMPTS = Path(__file__).resolve().parents[1] / "benchmarks" / "prompts"


def load_cases() -> list[dict[str, Any]]:
    return json.loads(BENCHMARK_CASES.read_text(encoding="utf-8"))


def benchmark_result(memory: Memory) -> MemorySearchResult:
    return MemorySearchResult(memory=memory, rank_score=1.0, text_rank=0.5, recency_score=0.5)


class BenchmarkRetriever:
    def __init__(self, case: dict[str, Any]) -> None:
        self.case = case
        self.calls: list[dict[str, Any]] = []
        self.memories = [self._memory(item) for item in case["memories"]]

    def search_memories(self, **kwargs: Any) -> list[MemorySearchResult]:
        self.calls.append(kwargs)
        return self._results(kwargs)

    def search_project_and_global_memories(self, project: str, **kwargs: Any) -> list[MemorySearchResult]:
        self.calls.append({"project": project, **kwargs})
        return self._results(kwargs)

    def search_hierarchical_memories(self, **kwargs: Any) -> list[MemorySearchResult]:
        self.calls.append(kwargs)
        component = kwargs.get("component")
        if self.case.get("empty_first_component") and component == self.case.get("component"):
            return []
        return self._results(kwargs)

    def search_scope_path_memories(self, **kwargs: Any) -> list[MemorySearchResult]:
        self.calls.append(kwargs)
        return self._results(kwargs)

    def _memory(self, item: dict[str, Any]) -> Memory:
        return Memory(
            id=uuid4(),
            memory_type=item["memory_type"],
            summary=item["summary"],
            content=item["content"],
            applies_to=item.get("applies_to") or {},
            sensitivity=item.get("sensitivity", "normal"),
            confidence="0.9",
        )

    def _results(self, kwargs: dict[str, Any]) -> list[MemorySearchResult]:
        memory_types = set(kwargs.get("memory_types") or [])
        sensitivities = set(kwargs.get("sensitivities") or [])
        matches = []
        for memory in self.memories:
            if memory_types and memory.memory_type not in memory_types:
                continue
            if sensitivities and memory.sensitivity not in sensitivities:
                continue
            matches.append(benchmark_result(memory))
        return matches


def test_benchmark_cases_are_task_oriented() -> None:
    cases = load_cases()
    categories = {case["category"] for case in cases}

    assert {"feature_work", "bug_fix", "validation_planning"}.issubset(categories)
    assert "information_regurgitation" not in categories
    assert {"outline", "ai-os-discord"}.issubset({case["project"] for case in cases})


def test_benchmark_cases_include_complex_feature_updates() -> None:
    complex_feature_updates = [
        case
        for case in load_cases()
        if case["category"] == "feature_update" and case.get("complexity") == "complex"
    ]

    assert len(complex_feature_updates) >= 2
    for case in complex_feature_updates:
        assert len(case.get("touchpoints", [])) >= 3
        assert {"api", "authorization", "tests"}.issubset(set(case["touchpoints"]))


def test_outline_benchmark_prompts_exist_for_cases() -> None:
    prompt_files = sorted(path for path in BENCHMARK_PROMPTS.glob("*.md") if path.name != "README.md")
    prompt_text_by_path = {path: path.read_text(encoding="utf-8") for path in prompt_files}
    prompt_text = "\n".join(prompt_text_by_path.values())

    case_prompt_files = [
        path
        for path in prompt_files
        if not path.name.startswith(("04-", "07-", "08-", "09-", "10-", "11-", "12-", "13-"))
    ]
    assert len(case_prompt_files) == len(load_cases()) * 2
    assert "D:\\git\\ai\\outline" in prompt_text
    assert "D:\\git\\ai\\outline-benchmarks" in prompt_text
    assert "git -C $source worktree add -B $branch $workspace origin/main" in prompt_text
    for case in load_cases():
        case_prompts = {
            path: text
            for path, text in prompt_text_by_path.items()
            if path in case_prompt_files
            if case["id"] in text
        }
        assert len(case_prompts) == 2
        assert any("variant: baseline" in text for text in case_prompts.values())
        assert any("variant: memory" in text for text in case_prompts.values())
        memory_prompt = "\n".join(text for text in case_prompts.values() if "variant: memory" in text)
        assert f'project="{case["project"]}"' in memory_prompt
        assert "memory_used: yes" in memory_prompt
        assert "`source_read_limits`" in memory_prompt or "source_read_limits" in memory_prompt
        assert "source_files_read_count:" in memory_prompt
        assert "source_snippets_read_count:" in memory_prompt
        assert "source_budget_exception:" in memory_prompt
        if case["category"] in {"feature_work", "bug_fix", "feature_update"}:
            assert "path-only fallback search does not authorize large source-output reads" in memory_prompt
            assert "After path-only discovery, read only bounded snippets from selected files" in memory_prompt
            assert "max_snippet_lines_obeyed: yes/no" in memory_prompt
            assert "oversized snippets before first edit mean `source_read_budget_obeyed: no`" in memory_prompt
        if case["category"] in {"feature_work", "bug_fix"}:
            for prompt in case_prompts.values():
                assert "Avoid whole-file formatting or line-ending rewrites unrelated to the fix" in prompt
                assert "formatter checks first" in prompt
                assert "formatting_churn: none/limited/broad" in prompt
                assert "`none` means no unrelated formatting or line-ending churn" in prompt
                assert "`limited` means formatter changes are confined to intentionally touched hunks/files" in prompt
                assert "`broad` means whole-file formatting, line-ending rewrites, or very large same-file diffs unrelated to the fix" in prompt
                assert "fallback_search_mode: none/path_only/content_dump" in prompt
                assert "fallback_search_commands:" in prompt
                assert "broad_search_output_stopped: yes/no/n/a" in prompt
        baseline_prompt = "\n".join(text for text in case_prompts.values() if "variant: baseline" in text)
        assert "Do not call `memory-mcp`" in baseline_prompt
        assert "memory_used: no" in baseline_prompt
        assert "memory_used: yes" not in baseline_prompt
        memory_prompt = "\n".join(text for text in case_prompts.values() if "variant: memory" in text)
        if case["category"] in {"feature_work", "bug_fix"}:
            assert "Baseline rules override repo/project AGENTS memory workflow" in baseline_prompt
            assert "stop and report the run as invalid instead of continuing with memory" in baseline_prompt
            assert "benchmark_invalid: yes/no" in baseline_prompt
            assert "accidental source-output fallback means the source-read budget was not obeyed" in memory_prompt


def test_product_improvement_prompt_uses_saved_results() -> None:
    prompt = (BENCHMARK_PROMPTS / "04-memory-mcp-improvement-plan-from-results.md").read_text(
        encoding="utf-8"
    )

    assert "D:\\git\\ai\\memory-mcp" in prompt
    assert "This is a planning task only. Do not edit code." in prompt
    assert "source-read budget noncompliance as the main product failure" in prompt
    assert "Preserve the behaviors that worked: sensitive memory exclusion and component" in prompt
    assert "outline_feature_api_collection_invites-comparison.md" in prompt
    assert "outline_bug_fix_search_authorization-comparison.md" in prompt
    assert "outline_validation_plan_wrong_component_fallback-comparison.md" in prompt
    assert "IMPROVEMENT_PLAN_RESULT" in prompt


def test_strict_fallback_implementation_prompt_captures_latest_failures() -> None:
    prompt = (
        BENCHMARK_PROMPTS / "04-memory-mcp-implementation-prompt-strict-fallback-and-baseline-isolation.md"
    ).read_text(encoding="utf-8")

    assert "git grep -n" in prompt
    assert "stop immediately" in prompt
    assert "fallback_search_mode: none/path_only/content_dump" in prompt
    assert "benchmark_invalid: yes/no" in prompt
    assert "Baseline rules override repo/project AGENTS memory workflow" in prompt
    assert "fallback_source_output_counts_as_budget_failure" in prompt
    assert "formatting_churn: none/limited/broad" in prompt


def test_codex_benchmark_loop_prompt_executes_runner_and_collates_results() -> None:
    prompt = (BENCHMARK_PROMPTS / "07-codex-run-outline-benchmark-loop.md").read_text(
        encoding="utf-8"
    )

    assert "benchmarks\\run_outline_benchmarks.py" in prompt
    assert "--apply-improvement-prompt" in prompt
    assert "--update-docker" in prompt
    assert "--iterations 2" in prompt
    assert "summary.json" in prompt
    assert "collated-analysis.md" in prompt
    assert "BENCHMARK_LOOP_RESULT" in prompt


def test_token_budgeted_benchmark_loop_prompt_runs_review_and_fix_prompt_loop() -> None:
    prompt = (BENCHMARK_PROMPTS / "13-codex-token-budgeted-outline-benchmark-loop.md").read_text(
        encoding="utf-8"
    )

    assert "benchmarks\\run_outline_benchmarks.py" in prompt
    assert "--mode targeted" in prompt
    assert "--dry-run" in prompt
    assert "--allow-large-token-run" in prompt
    assert "--keep-full-artifacts" in prompt
    assert "stdout-tail.txt" in prompt
    assert "summary.json" in prompt
    assert "collated-analysis.md" in prompt
    assert "fix-prompt.md" in prompt
    assert "BENCHMARK_LOOP_RESULT" in prompt


def test_complex_memory_prompts_require_pre_edit_budget_accounting() -> None:
    prompt_names = [
        "05b-memory-outline-feature-update-collection-default-permissions.md",
        "06b-memory-outline-feature-update-comment-resolution-audit.md",
    ]

    for prompt_name in prompt_names:
        prompt = (BENCHMARK_PROMPTS / prompt_name).read_text(encoding="utf-8")

        assert "distinguish path-only discovery from source snippet reads" in prompt
        assert "record the files/snippets read before the first edit" in prompt
        assert "pre-edit budget checkpoint" in prompt
        assert "named a missing fact" in prompt
        assert "Your objective is to obey the pre-edit limits" in prompt
        assert "A recorded exception explains budget failure; it does not preserve compliance" in prompt
        assert "source_read_budget_obeyed: no" in prompt
        assert "pre_edit_budget_checkpoint_hit: yes/no" in prompt
        assert "extra_pre_edit_reads_exception_recorded: yes/no/n/a" in prompt
        assert "pre_edit_source_files_read_count:" in prompt
        assert "pre_edit_source_snippets_read_count:" in prompt
        assert "max_snippet_lines_obeyed: yes/no" in prompt
        assert "path-only fallback search does not authorize large source-output reads" in prompt
        assert "After path-only discovery, read only bounded snippets from selected files" in prompt
        assert "oversized snippets before first edit mean `source_read_budget_obeyed: no`" in prompt
        assert "fallback_search_mode: none/path_only/content_dump" in prompt
        assert "formatting_churn: none/limited/broad" in prompt


def test_memory_prompts_require_pre_edit_snippet_count_compliance() -> None:
    prompt_names = [
        "01b-memory-outline-feature-api-collection-invites.md",
        "02b-memory-outline-bugfix-search-private-title-leak.md",
        "05b-memory-outline-feature-update-collection-default-permissions.md",
        "06b-memory-outline-feature-update-comment-resolution-audit.md",
    ]

    for prompt_name in prompt_names:
        prompt = (BENCHMARK_PROMPTS / prompt_name).read_text(encoding="utf-8")

        assert "Bounded snippets still count toward `source_read_limits.max_snippets`" in prompt
        assert "Staying under `source_read_limits.max_lines_per_snippet` is not enough" in prompt
        assert "Stop at `source_read_limits.max_snippets` before the first edit" in prompt
        assert "inspect only the top few directly implicated files/snippets" in prompt
        assert "name the missing fact, likely file/symbol, and why the current bounded snippets are insufficient" in prompt
        assert "Exceeding `source_read_limits.max_snippets` before first edit means `source_read_budget_obeyed: no`" in prompt


def test_security_audit_prompt_covers_provider_neutral_authentication() -> None:
    prompt = (BENCHMARK_PROMPTS / "09-memory-mcp-security-audit-authentication.md").read_text(
        encoding="utf-8"
    )

    assert "trusted local stdio development without authentication" in prompt
    assert "provider-neutral principal and authorization interface" in prompt
    assert "Okta" in prompt
    assert "Microsoft Entra ID" in prompt
    assert "Google Workspace" in prompt
    assert "Auth0" in prompt
    assert "Keycloak" in prompt
    assert "reverse-proxy identity" in prompt
    assert "SECURITY_AUDIT_RESULT" in prompt


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: case["id"])
def test_context_packet_benchmark_case(case: dict[str, Any]) -> None:
    retriever = BenchmarkRetriever(case)
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context(
        case["request"],
        workspace=case.get("workspace"),
        project=case.get("project"),
        component=case.get("component"),
        max_memories=case.get("max_memories", 8),
        max_tokens=case.get("max_tokens"),
    )

    expected = case["expected"]
    rendered_facts = "\n".join(packet.facts)
    diagnostics = packet.diagnostics

    assert packet.classification.domain == expected["domain"]
    assert diagnostics["context_quality"] == expected["context_quality"]
    assert diagnostics["suggested_next_action"] == expected["suggested_next_action"]
    assert diagnostics["source_read_policy"] == expected["source_read_policy"]
    assert diagnostics["source_read_budget_tokens"] >= expected["min_source_read_budget_tokens"]
    assert diagnostics["source_read_limits"]["source_read_budget_tokens"] == diagnostics["source_read_budget_tokens"]
    assert diagnostics["source_read_limits"]["broad_read_disallowed"] is True
    assert packet.token_reduction_percent >= expected["min_token_reduction_percent"]
    # render() now emits only the slim 3-line guidance summary (commit 42922e6); the
    # full limits/contract are asserted above via packet.diagnostics.
    assert "## Source Read Guidance" in packet.render()

    for snippet in expected.get("facts_include", []):
        assert snippet in rendered_facts
    for snippet in expected.get("facts_exclude", []):
        assert snippet not in rendered_facts
    for scope in expected.get("matched_scopes_include", []):
        assert scope in diagnostics["matched_scopes"]
    for memory_type in expected.get("matched_memory_types_exclude", []):
        assert memory_type not in diagnostics["matched_memory_types"]

    if case["category"] in {"feature_work", "bug_fix"}:
        assert diagnostics["implementation_request"] is True
        assert diagnostics["source_read_limits"]["max_files_before_edit"] == 8
        assert diagnostics["source_read_limits"]["max_snippets"] == 10
    if "fallback_accepted" in expected:
        assert any(attempt["accepted"] is expected["fallback_accepted"] for attempt in diagnostics["fallback_attempts"])
