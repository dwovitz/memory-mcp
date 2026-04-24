"""Context packet synthesis tests."""

from __future__ import annotations

from uuid import uuid4

from memory_mcp.models import Memory
from memory_mcp.retrieval import MemorySearchResult
from memory_mcp.services import ContextSynthesisService


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
) -> Memory:
    return Memory(
        id=uuid4(),
        memory_type=memory_type,
        summary=summary,
        content=content,
        evidence=evidence or [],
        metadata_={"seed": True, "verbose": "x" * 200},
        applies_to={"scope": "development"},
        confidence="0.9",
    )


def test_classifies_project_request_and_excludes_unrelated_domains() -> None:
    retriever = FakeRetriever([])
    service = ContextSynthesisService(retriever=retriever)

    packet = service.synthesize_context("What should I remember for this Python project?")

    call = retriever.calls[0]
    assert packet.classification.domain == "project"
    assert call["memory_types"] == ("project_fact", "app_knowledge", "coding_preference")
    assert call["scope"] is None
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
    assert call["memory_types"] == ("project_fact", "app_knowledge", "coding_preference")


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
