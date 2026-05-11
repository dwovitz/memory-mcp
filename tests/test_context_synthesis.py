"""Context packet synthesis tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from memory_mcp.models import Memory
from memory_mcp.retrieval import MemorySearchResult, PROJECT_CONTEXT_MEMORY_TYPES
from memory_mcp.services import ContextSynthesisService
from memory_mcp.services.context_synthesis import SOURCE_READ_LIMITS_BY_POLICY


class FakeRetriever:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def search_memories(self, **kwargs):
        self.calls.append(kwargs)
        return self.results

    def search_project_and_global_memories(self, project, **kwargs):
        self.calls.append({"project": project, **kwargs})
        return self.results

    def search_hierarchical_memories(self, **kwargs):
        self.calls.append(kwargs)
        return self.results

    def search_scope_path_memories(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


def result(memory: Memory) -> MemorySearchResult:
    return MemorySearchResult(memory=memory, rank_score=1.0, text_rank=0.5, recency_score=0.5)


def memory(
    memory_type: str,
    *,
    summary: str,
    content: str,
    evidence=None,
    applies_to=None,
) -> Memory:
    return Memory(
        id=uuid4(),
        memory_type=memory_type,
        summary=summary,
        content=content,
        evidence=evidence or [],
        metadata_={"seed": True, "verbose": "x" * 200},
        applies_to=applies_to or {"scope": "development"},
        confidence="0.9",
    )


def test_classifies_project_request_and_excludes_unrelated_domains() -> None:
    retriever = FakeRetriever([])
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context("What should I remember for this Python project?")

    call = retriever.calls[0]
    assert packet.classification.domain == "project"
    assert call["memory_types"] == PROJECT_CONTEXT_MEMORY_TYPES
    assert call["scope"] is None
    assert "medication" not in call["memory_types"]
    assert "entertainment_preference" not in call["memory_types"]


def test_project_request_includes_rich_project_context_types() -> None:
    retriever = FakeRetriever([])
    service = ContextSynthesisService(retriever=retriever)

    service.synthesize_context("Repo outline for orienting a coding agent to backend API changes.")

    call = retriever.calls[0]
    assert {
        "component_summary",
        "architecture_decision",
        "project_rule",
        "workflow_location",
        "dependency",
        "external_reference",
    }.issubset(call["memory_types"])
    assert "medication" not in call["memory_types"]
    assert "entertainment_preference" not in call["memory_types"]
    assert "inferred_preference" not in call["memory_types"]


def test_explicit_project_scope_promotes_architecture_risk_prompt() -> None:
    retriever = FakeRetriever([])
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context(
        "Architecture, correctness, authorization, security, and performance risks before changing an authenticated backend API endpoint.",
        workspace="ai",
        project="outline",
        component="backend",
    )

    call = retriever.calls[0]
    assert packet.classification.domain == "project"
    assert call["memory_types"] == PROJECT_CONTEXT_MEMORY_TYPES
    assert "medication" not in call["memory_types"]
    assert "entertainment_preference" not in call["memory_types"]


def test_synthesis_prefers_summary_unless_detail_requested() -> None:
    project_memory = memory(
        "project_fact",
        summary="memory-mcp uses PostgreSQL and pgvector.",
        content="memory-mcp is a local-first MCP server using Dockerized PostgreSQL with pgvector and a Python host process.",
    )
    retriever = FakeRetriever([result(project_memory)])
    service = ContextSynthesisService(retriever=retriever)

    compact_packet = service.synthesize_context("What should I know about this project?")
    detailed_packet = service.synthesize_context("Give me details about this project")

    assert compact_packet.facts == ["memory-mcp uses PostgreSQL and pgvector."]
    assert "Detail:" not in compact_packet.render()
    assert "Detail:" in detailed_packet.render()


def test_output_groups_preferences_facts_and_episodic_context() -> None:
    retriever = FakeRetriever(
        [
            result(memory("coding_preference", summary="Prefer small modules.", content="Prefer small modular Python changes.")),
            result(memory("project_fact", summary="Runs locally on Windows.", content="Runs locally on Windows with Docker.")),
            result(memory("event", summary="Discussed schema design.", content="Discussed schema design during setup.")),
        ]
    )
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context("project context")

    assert packet.preferences == ["Prefer small modules."]
    assert packet.facts == ["Runs locally on Windows."]
    assert packet.episodic_context == ["Discussed schema design."]
    rendered = packet.render()
    assert "## Preferences" in rendered
    assert "## Facts" in rendered
    assert "## Episodic Context" in rendered


def test_synthesized_packet_can_include_rich_project_memory_type() -> None:
    architecture_memory = memory(
        "component_summary",
        summary="The web client uses React Router, MobX stores, and lazy-loaded routes.",
        content="Outline app routes are split by auth state and lazy loaded through React Router.",
    )
    retriever = FakeRetriever([result(architecture_memory)])
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context("Repo outline for orienting a coding agent to Outline.")

    assert packet.facts == ["The web client uses React Router, MobX stores, and lazy-loaded routes."]


def test_optional_evidence_and_token_reduction() -> None:
    memory_with_evidence = memory(
        "project_fact",
        summary="Uses SQLAlchemy.",
        content="The project uses SQLAlchemy for database sessions and query construction.",
        evidence=[{"kind": "explicit", "text": "Dependency added in pyproject.", "source": "seed"}],
    )
    retriever = FakeRetriever([result(memory_with_evidence)])
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context("project details with evidence", include_evidence=True)

    assert packet.evidence == ["project_fact: explicit: Dependency added in pyproject. Source: seed"]
    assert packet.before_token_estimate > packet.after_token_estimate
    assert packet.token_reduction_percent > 0


def test_health_requests_include_detail_for_medications() -> None:
    retriever = FakeRetriever(
        [
            result(
                memory(
                    "medication",
                    summary="Example cetirizine medication memory.",
                    content="Synthetic example: Alex takes cetirizine 10 mg in the evening.",
                )
            )
        ]
    )
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context("What medication dose should I know?")

    assert packet.classification.domain == "health"
    assert "Detail:" in packet.render()
    assert retriever.calls[0]["tags"] == ("health",)


def test_project_scoped_synthesis_uses_project_and_global_search() -> None:
    retriever = FakeRetriever([])
    service = ContextSynthesisService(retriever=retriever)

    service.synthesize_context(
        "What should I remember for this Python project?",
        project="memory-mcp",
        include_global=True,
    )

    call = retriever.calls[0]
    assert call["project"] == "memory-mcp"
    assert call["include_global"] is True
    assert call["memory_types"] == PROJECT_CONTEXT_MEMORY_TYPES


def test_component_scoped_synthesis_passes_workspace_and_component() -> None:
    retriever = FakeRetriever([])
    service = ContextSynthesisService(retriever=retriever)

    service.synthesize_context(
        "What should I remember while changing auth in this Python project?",
        workspace="corp-root",
        project="payments-api",
        component="auth",
        topic="sessions",
        include_global=True,
    )

    call = retriever.calls[0]
    assert call["workspace"] == "corp-root"
    assert call["project"] == "payments-api"
    assert call["component"] == "auth"
    assert call["topic"] == "sessions"


def test_weak_component_packet_retries_project_scope_with_diagnostics() -> None:
    calls = []
    workspace_memory = memory(
        "project_fact",
        summary="The ai workspace contains sibling app repositories.",
        content="The ai workspace contains sibling app repositories.",
        applies_to={"memory_scope": "workspace", "workspace": "ai"},
    )
    auth_memory = memory(
        "component_summary",
        summary="Auth middleware validates JWT, API key, and OAuth token credentials.",
        content="Auth middleware validates JWT, API key, and OAuth token credentials.",
        applies_to={
            "memory_scope": "component",
            "workspace": "ai",
            "project": "outline",
            "component": "auth",
        },
    )

    class ComponentFallbackRetriever:
        def search_hierarchical_memories(self, **kwargs):
            calls.append(kwargs)
            if kwargs.get("component") == "backend":
                return [result(workspace_memory)]
            if kwargs.get("component") is None:
                return [result(auth_memory), result(workspace_memory)]
            return []

    service = ContextSynthesisService(retriever=ComponentFallbackRetriever())

    packet = service.synthesize_context(
        "Architecture, correctness, authorization, security, and performance risks before adding an authenticated backend API endpoint in Outline.",
        workspace="ai",
        project="outline",
        component="backend",
        max_memories=10,
        max_tokens=1200,
    )

    assert [call.get("component") for call in calls] == ["backend", None]
    assert packet.facts[0] == "Auth middleware validates JWT, API key, and OAuth token credentials."
    assert packet.diagnostics["context_quality"] == "usable"
    assert packet.diagnostics["fallback_attempts"][0]["accepted"] is True
    assert packet.diagnostics["matched_scopes"] == ["component:outline/auth", "workspace:ai"]
    assert packet.diagnostics["has_project_scoped_facts"] is True
    assert packet.diagnostics["has_component_scoped_facts"] is True
    assert packet.diagnostics["has_direct_component_facts"] is False
    assert packet.diagnostics["suggested_next_action"] == "verify_narrowly"
    assert packet.diagnostics["source_read_policy"] == "focused_snippets"
    assert packet.diagnostics["source_read_budget_tokens"] == 2000
    assert packet.diagnostics["source_read_limits"]["max_files_before_edit"] == 4
    assert packet.diagnostics["source_read_limits"]["max_snippets"] == 6
    assert packet.diagnostics["source_read_limits"]["max_lines_per_snippet"] == 40
    assert any("Fallback broadened retrieval" in warning for warning in packet.diagnostics["warnings"])
    assert "## Source Read Guidance" in packet.render()
    assert "Recommended post-packet source budget: 2000 tokens." in packet.render()
    rendered = packet.render()
    assert "If fast search such as rg is unavailable, run path-only search first before reading snippets" in rendered
    assert rendered.index("path-only search first") < rendered.index("read only bounded snippets")
    assert "Broad recursive source-output dumps are disallowed as a substitute for search" in rendered


def test_project_packet_with_only_workspace_context_marks_weak_context() -> None:
    workspace_memory = memory(
        "project_fact",
        summary="The ai workspace contains sibling app repositories.",
        content="The ai workspace contains sibling app repositories.",
        applies_to={"memory_scope": "workspace", "workspace": "ai"},
    )
    retriever = FakeRetriever([result(workspace_memory)])
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context(
        "Architecture risks before changing an authenticated backend API endpoint.",
        workspace="ai",
        project="outline",
    )

    assert packet.diagnostics["context_quality"] == "weak"
    assert packet.diagnostics["only_workspace_or_global_facts"] is True
    assert packet.diagnostics["suggested_next_action"] == "mark_weak_context"
    assert packet.diagnostics["source_read_policy"] == "none"
    assert packet.diagnostics["source_read_budget_tokens"] == 0
    assert packet.diagnostics["source_read_limits"]["source_content_allowed"] is False


def test_strong_broad_project_packet_recommends_answering_from_packet() -> None:
    project_memory = memory(
        "project_fact",
        summary=(
            "Outline backend APIs use policy checks in route handlers, validate request "
            "schemas, and keep persistence changes behind service/model boundaries."
        ),
        content=(
            "Outline backend APIs use policy checks in route handlers, validate request "
            "schemas, and keep persistence changes behind service/model boundaries."
        ),
        applies_to={"memory_scope": "project", "workspace": "ai", "project": "outline"},
    )
    retriever = FakeRetriever([result(project_memory)])
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context(
        "Security and authorization risks for an authenticated backend API endpoint.",
        workspace="ai",
        project="outline",
    )

    assert packet.diagnostics["context_quality"] == "strong"
    assert packet.diagnostics["suggested_next_action"] == "answer_from_packet"
    assert packet.diagnostics["source_read_policy"] == "path_enum_only"
    assert packet.diagnostics["source_read_budget_tokens"] == 0
    assert packet.diagnostics["source_read_limits"]["path_enum_allowed"] is True
    assert packet.diagnostics["source_read_limits"]["source_content_allowed"] is False
    assert packet.diagnostics["source_read_limits"]["path_only_search_first"] is True
    assert packet.diagnostics["source_read_limits"]["broad_fallback_search_disallowed"] is True
    assert "git grep -l <term>" in packet.diagnostics["source_read_limits"]["fallback_search_examples"]


def test_source_read_guidance_separates_discovery_from_bounded_snippets() -> None:
    project_memory = memory(
        "project_fact",
        summary="Outline backend changes start from path discovery and bounded snippets.",
        content="Outline backend changes start from path discovery and bounded snippets.",
        applies_to={"memory_scope": "project", "workspace": "ai", "project": "outline"},
    )
    retriever = FakeRetriever([result(project_memory)])
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context(
        "Implement a backend API change in Outline.",
        workspace="ai",
        project="outline",
    )

    rendered = packet.render()
    limits = packet.diagnostics["source_read_limits"]
    assert limits["path_only_discovery_only"] is True
    assert limits["select_string_list_only_for_discovery"] is True
    assert limits["bounded_snippets_after_discovery"] is True
    assert limits["oversized_snippet_counts_as_budget_failure"] is True
    assert limits["discard_oversized_snippet_output"] is True
    assert limits["snippet_count_limit_is_hard"] is True
    assert limits["bounded_snippets_still_count_toward_budget"] is True
    assert limits["stop_at_max_snippets_before_edit"] is True
    assert limits["exceeding_snippet_count_counts_as_budget_failure"] is True
    assert "Path-only commands are discovery-only" in rendered
    assert "Select-String -List is allowed only when listing matching files for discovery" in rendered
    assert "Select-String output with matching source lines is a source snippet read" in rendered
    assert "After discovery, read only bounded snippets from selected files" in rendered
    assert "discard oversized snippet output" in rendered
    assert "count the incident as a source-read budget failure" in rendered
    assert "Bounded snippets still count toward source_read_limits.max_snippets" in rendered
    assert "Staying under max_lines_per_snippet is not enough" in rendered
    assert "Stop at source_read_limits.max_snippets before the first edit" in rendered
    assert "Exceeding max_snippets before first edit means source_read_budget_obeyed: no" in rendered


def test_validation_plan_packet_uses_focused_snippet_budget_when_usable() -> None:
    api_memory = memory(
        "component_summary",
        summary=(
            "API tests cover authenticated route behavior with targeted endpoint "
            "fixtures, permission failures, schema validation, and unchanged "
            "unrelated route behavior."
        ),
        content=(
            "API tests cover authenticated route behavior with targeted endpoint "
            "fixtures, permission failures, schema validation, and unchanged "
            "unrelated route behavior."
        ),
        applies_to={
            "memory_scope": "component",
            "workspace": "ai",
            "project": "outline",
            "component": "api",
        },
    )

    class ValidationPlanRetriever:
        def search_hierarchical_memories(self, **kwargs):
            if kwargs.get("component") == "tests":
                return []
            return [result(api_memory)]

    service = ContextSynthesisService(retriever=ValidationPlanRetriever())

    packet = service.synthesize_context(
        "Focused validation plan for a change that adds or modifies an authenticated backend API endpoint.",
        workspace="ai",
        project="outline",
        component="tests",
        max_memories=10,
    )

    assert packet.diagnostics["context_quality"] == "usable"
    assert packet.diagnostics["broad_project_request"] is True
    assert packet.diagnostics["suggested_next_action"] == "verify_narrowly"
    assert packet.diagnostics["source_read_policy"] == "focused_snippets"
    assert packet.diagnostics["source_read_budget_tokens"] == 2000
    assert packet.diagnostics["source_read_limits"]["broad_read_disallowed"] is True


def test_implementation_packet_includes_concrete_source_read_limits() -> None:
    api_memory = memory(
        "component_summary",
        summary=(
            "Outline API routes validate request schemas, authorize against policies, "
            "and keep persistence changes behind service or model boundaries."
        ),
        content=(
            "Outline API routes validate request schemas, authorize against policies, "
            "and keep persistence changes behind service or model boundaries."
        ),
        applies_to={
            "memory_scope": "component",
            "workspace": "ai",
            "project": "outline",
            "component": "api",
        },
    )
    retriever = FakeRetriever([result(api_memory)])
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context(
        "Implement collection-level invite expiration settings in the Outline API.",
        workspace="ai",
        project="outline",
        component="api",
    )

    limits = packet.diagnostics["source_read_limits"]
    assert packet.diagnostics["suggested_next_action"] == "inspect_budget_then_edit"
    assert packet.diagnostics["source_read_policy"] == "implementation_required"
    assert packet.diagnostics["source_read_budget_tokens"] == 4000
    assert limits["max_files_before_edit"] == 8
    assert limits["max_snippets"] == 10
    assert limits["max_lines_per_snippet"] == 60
    assert limits["source_content_allowed"] is True
    assert limits["broad_read_disallowed"] is True
    assert limits["path_only_search_first"] is True
    assert limits["broad_fallback_search_disallowed"] is True
    assert limits["fallback_search_examples"] == [
        "git grep -l <term>",
        "grep -R -l <term> <candidate-dirs>",
        "git ls-files with targeted filtering",
        "Select-String -List over known candidate files",
    ]
    assert "git grep -n <term>" in limits["fallback_search_disallowed_examples"]
    assert "Select-String without -List for discovery" in limits["fallback_search_disallowed_examples"]
    assert limits["stop_on_source_output_fallback"] is True
    assert limits["fallback_source_output_counts_as_budget_failure"] is True
    assert limits["pre_edit_path_discovery_required"] is True
    assert limits["pre_edit_candidate_selection_required"] is True
    assert limits["pre_edit_budget_checkpoint_required"] is True
    assert limits["extra_pre_edit_reads_require_exception"] is True
    assert limits["extra_pre_edit_reads_count_as_budget_failure"] is True
    assert limits["pre_edit_checkpoint_default_action"] == "make_first_edit"
    assert limits["pre_edit_exception_preserves_budget_compliance"] is False
    assert limits["pre_edit_sequence"] == [
        "enumerate likely paths",
        "choose the top candidate files",
        "read only bounded snippets from those candidates",
        "stop at the budget checkpoint before reading more",
        "make the first edit or explicitly record a budget exception",
    ]
    assert "first edit" in limits["pre_edit_stop_rule"]
    assert "missing fact" in limits["pre_edit_expansion_rule"]
    contract = packet.diagnostics["source_read_contract"]
    assert contract["version"] == "source-read-contract/v1"
    assert contract["source_read_policy"] == "implementation_required"
    assert contract["suggested_next_action"] == "inspect_budget_then_edit"
    assert contract["pre_edit_limits"] == {
        "max_files": 8,
        "max_snippets": 10,
        "max_lines_per_snippet": 60,
    }
    assert contract["counting_rules"]["bounded_snippets_count_toward_max_snippets"] is True
    assert contract["counting_rules"]["path_only_discovery_counts_as_source_read"] is False
    assert contract["counting_rules"]["select_string_list_is_path_only_discovery"] is True
    assert contract["counting_rules"]["select_string_matches_count_as_snippets"] is True
    assert contract["counting_rules"]["oversized_snippet_counts_as_budget_failure"] is True
    assert contract["counting_rules"]["exceeding_max_snippets_counts_as_budget_failure"] is True
    assert contract["pre_edit_checkpoint"]["required"] is True
    assert contract["pre_edit_checkpoint"]["stop_at_max_snippets"] is True
    assert contract["pre_edit_checkpoint"]["default_action"] == "make_first_edit"
    assert contract["exception_rule"]["required_before_exceeding_budget"] is True
    assert contract["exception_rule"]["preserves_budget_compliance"] is False
    assert contract["exception_rule"]["must_name"] == [
        "missing_fact",
        "likely_file_or_symbol",
        "why_current_bounded_snippets_are_insufficient",
    ]
    assert "pre_edit_source_snippets_read_count > pre_edit_limits.max_snippets" in contract[
        "failure_conditions"
    ]
    assert "max_snippet_lines_obeyed == false" in contract["failure_conditions"]
    assert "source_read_budget_obeyed" in contract["reporting_fields"]
    rendered = packet.render()
    assert "Implementation workflow: enumerate likely paths" in rendered
    assert "choose the top candidate files" in rendered
    assert "stop at the budget checkpoint before reading more" in rendered
    assert "extra pre-edit reads require a recorded budget exception" in rendered
    assert "count as a budget failure" in rendered
    assert "default action is to make the first edit" in rendered
    assert "A recorded exception explains budget failure; it does not preserve compliance" in rendered
    assert "Do not read tests, model, route, presenter, policy, migration, and client files all up front" in rendered
    assert "Snippet size limits are hard pre-edit limits" in rendered
    assert rendered.index("path-only search first") < rendered.index("read only bounded snippets")
    assert "Fallback search examples: git grep -l <term>" in rendered
    assert "Disallowed fallback examples: git grep -n <term>" in rendered
    assert "If fallback search starts printing source lines, stop immediately" in rendered
    assert "Only exceed this budget after naming the missing fact" in rendered


def test_source_read_policy_names_remain_stable() -> None:
    assert set(SOURCE_READ_LIMITS_BY_POLICY) == {
        "none",
        "path_enum_only",
        "focused_snippets",
        "implementation_required",
    }


def test_scope_path_synthesis_uses_scoped_search() -> None:
    retriever = FakeRetriever([])
    service = ContextSynthesisService(retriever=retriever)

    service.synthesize_context(
        "What should I remember for attack buffering?",
        scope_path=["global", "project:Metroidvania", "branch:combat-refactor", "feature:attack-buffering"],
        include_inherited=True,
    )

    call = retriever.calls[0]
    assert call["scope_path"] == [
        "global",
        "project:Metroidvania",
        "branch:combat-refactor",
        "feature:attack-buffering",
    ]
    assert call["include_inherited"] is True


@pytest.fixture
def synthesis_service():
    return ContextSynthesisService(retriever=FakeRetriever([]))


def test_synthesis_respects_max_token_budget() -> None:
    retriever = FakeRetriever(
        [
            result(memory("project_fact", summary="Short fact.", content="Short fact.")),
            result(
                memory(
                    "project_fact",
                    summary="This second fact is long enough to exceed a tiny synthetic token budget.",
                    content="This second fact is long enough to exceed a tiny synthetic token budget.",
                )
            ),
        ]
    )
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context("project context", max_tokens=4)

    assert packet.facts == ["Short fact."]
    assert packet.after_token_estimate <= 4
    assert packet.token_budget == 4


def test_classification_exposes_matched_entities(synthesis_service) -> None:
    classification = synthesis_service.classify_request(
        "Why is UCX.RequestRouting not routing cases correctly?"
    )
    assert hasattr(classification, "matched_entities")
    assert hasattr(classification, "hinted_repos")
    assert hasattr(classification, "hinted_memory_types")


def test_classification_matched_entities_is_list(synthesis_service) -> None:
    classification = synthesis_service.classify_request("general question")
    assert isinstance(classification.matched_entities, list)
    assert isinstance(classification.hinted_repos, list)
    assert isinstance(classification.hinted_memory_types, list)
