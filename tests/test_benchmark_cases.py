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
    assert {case["project"] for case in cases} == {"outline"}


def test_outline_benchmark_prompts_exist_for_cases() -> None:
    prompt_files = sorted(path for path in BENCHMARK_PROMPTS.glob("*.md") if path.name != "README.md")
    prompt_text_by_path = {path: path.read_text(encoding="utf-8") for path in prompt_files}
    prompt_text = "\n".join(prompt_text_by_path.values())

    case_prompt_files = [path for path in prompt_files if not path.name.startswith("04-")]
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
        assert 'project="outline"' in memory_prompt
        assert "memory_used: yes" in memory_prompt
        assert "`source_read_limits`" in memory_prompt or "source_read_limits" in memory_prompt
        assert "source_files_read_count:" in memory_prompt
        assert "source_snippets_read_count:" in memory_prompt
        assert "source_budget_exception:" in memory_prompt
        if case["category"] in {"feature_work", "bug_fix"}:
            for prompt in case_prompts.values():
                assert "Avoid whole-file formatting or line-ending rewrites unrelated to the fix" in prompt
                assert "formatter checks first" in prompt
                assert "formatting_churn: none/limited/broad" in prompt
        baseline_prompt = "\n".join(text for text in case_prompts.values() if "variant: baseline" in text)
        assert "Do not call `memory-mcp`" in baseline_prompt
        assert "memory_used: no" in baseline_prompt


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
    assert "## Source Read Guidance" in packet.render()
    assert "Source read limits:" in packet.render()

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
        assert "If fast search such as rg is unavailable" in packet.render()
