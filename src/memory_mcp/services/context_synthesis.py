"""Synthesize compact LLM-ready context packets from memories."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy.orm import Session

from memory_mcp.models import Memory
from memory_mcp.retrieval import (
    HybridRetrievalService,
    MemorySearchResult,
    PROJECT_CONTEXT_MEMORY_TYPES,
)
from memory_mcp.scopes import (
    COMPONENT_KEY,
    COMPONENT_MEMORY_SCOPE,
    GLOBAL_MEMORY_SCOPE,
    PROJECT_KEY,
    PROJECT_MEMORY_SCOPE,
    SCOPE_PATH_KEY,
    TOPIC_KEY,
    WORKSPACE_KEY,
    WORKSPACE_MEMORY_SCOPE,
    with_memory_scope,
    without_applies_to_keys,
)


class MemoryRetriever(Protocol):
    """Subset of retrieval behavior needed by context synthesis."""

    def search_memories(self, **kwargs: Any) -> list[MemorySearchResult]:
        """Search memories using structured and lexical filters."""


@dataclass(frozen=True)
class RequestClassification:
    """Heuristic request classification used to constrain retrieval."""

    domain: str
    memory_types: tuple[str, ...]
    scope: str | None = None
    tags: tuple[str, ...] | None = None
    include_detail: bool = False
    rationale: str = ""


@dataclass(frozen=True)
class ContextPacket:
    """Synthesized context packet plus reduction metadata."""

    request: str
    classification: RequestClassification
    preferences: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    episodic_context: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    before_token_estimate: int = 0
    after_token_estimate: int = 0
    token_budget: int | None = None

    @property
    def token_reduction_percent(self) -> float:
        if self.before_token_estimate == 0:
            return 0.0
        saved = self.before_token_estimate - self.after_token_estimate
        return max(0.0, (saved / self.before_token_estimate) * 100)

    def render(self) -> str:
        sections = [
            "# Context Packet",
            f"Request domain: {self.classification.domain}",
        ]
        if self.preferences:
            sections.extend(["", "## Preferences", *_bullet_lines(self.preferences)])
        if self.facts:
            sections.extend(["", "## Facts", *_bullet_lines(self.facts)])
        if self.episodic_context:
            sections.extend(["", "## Episodic Context", *_bullet_lines(self.episodic_context)])
        if self.evidence:
            sections.extend(["", "## Evidence", *_bullet_lines(self.evidence)])
        sections.extend(
            [
                "",
                "## Token Estimate",
                f"Before: {self.before_token_estimate}",
                f"After: {self.after_token_estimate}",
                f"Budget: {self.token_budget}" if self.token_budget is not None else "Budget: none",
                f"Reduction: {self.token_reduction_percent:.1f}%",
            ]
        )
        return "\n".join(sections)


class ContextSynthesisService:
    """Generate minimal context packets for LLM prompts."""

    def __init__(
        self,
        session: Session | None = None,
        *,
        retriever: MemoryRetriever | None = None,
    ) -> None:
        if retriever is None and session is None:
            raise ValueError("Either session or retriever is required")
        self.retriever = retriever or HybridRetrievalService(session)  # type: ignore[arg-type]

    def classify_request(self, request: str) -> RequestClassification:
        normalized = request.lower()
        wants_detail = any(
            word in normalized
            for word in ("detail", "details", "evidence", "why", "exact", "dose", "dosage", "full")
        )

        if _contains_any(normalized, ("medication", "medicine", "dose", "allergy", "health")):
            return RequestClassification(
                domain="health",
                memory_types=("medication", "personal_fact"),
                tags=("health",),
                include_detail=True,
                rationale="Health requests need medication facts and enough detail to avoid ambiguity.",
            )
        if _contains_any(normalized, ("show", "movie", "genre", "watch", "entertainment", "liked", "disliked")):
            return RequestClassification(
                domain="entertainment",
                memory_types=("entertainment_preference", "inferred_preference"),
                scope="entertainment",
                include_detail=wants_detail,
                rationale="Entertainment requests should exclude project, device, and medication domains.",
            )
        if _contains_any(normalized, ("project", "code", "coding", "repo", "app", "mcp", "python")):
            return RequestClassification(
                domain="project",
                memory_types=PROJECT_CONTEXT_MEMORY_TYPES,
                include_detail=wants_detail,
                rationale="Project requests need app, architecture, and coding preference context.",
            )
        if _contains_any(normalized, ("partner", "person", "people", "who", "personal")):
            return RequestClassification(
                domain="personal",
                memory_types=("personal_fact",),
                scope="personal",
                include_detail=wants_detail,
                rationale="Personal requests should focus on people facts only.",
            )
        return RequestClassification(
            domain="general",
            memory_types=(
                "personal_fact",
                "project_fact",
                "app_knowledge",
                "coding_preference",
                "entertainment_preference",
                "inferred_preference",
            ),
            include_detail=wants_detail,
            rationale="General requests use a broad but still active-memory-only set.",
        )

    def synthesize_context(
        self,
        request: str,
        *,
        include_evidence: bool = False,
        max_memories: int = 8,
        applies_to: dict[str, Any] | None = None,
        sensitivities: Sequence[str] | None = ("normal",),
        workspace: str | None = None,
        project: str | None = None,
        component: str | None = None,
        topic: str | None = None,
        include_global: bool = True,
        scope_path: Sequence[str] | None = None,
        include_inherited: bool = True,
        max_tokens: int | None = None,
    ) -> ContextPacket:
        classification = self.classify_request(request)
        search_kwargs = {
            "text_query": request,
            "memory_types": classification.memory_types,
            "statuses": ("active",),
            "tags": classification.tags,
            "scope": classification.scope,
            "applies_to": applies_to,
            "sensitivities": sensitivities,
            "min_confidence": Decimal("0.5"),
            "limit": max_memories,
        }
        results = self._search_relevant_memories(
            workspace=workspace,
            project=project,
            component=component,
            topic=topic,
            include_global=include_global,
            scope_path=scope_path,
            include_inherited=include_inherited,
            **search_kwargs,
        )
        memories = [result.memory for result in results]

        preferences: list[str] = []
        facts: list[str] = []
        episodic_context: list[str] = []
        evidence_items: list[str] = []
        token_parts: list[str] = []

        for memory in memories:
            line = _memory_line(memory, include_detail=classification.include_detail)
            category = _packet_category(memory.memory_type)
            if category == "preferences":
                if not _fits_token_budget(token_parts, line, max_tokens=max_tokens):
                    break
                preferences.append(line)
            elif category == "episodic":
                if not _fits_token_budget(token_parts, line, max_tokens=max_tokens):
                    break
                episodic_context.append(line)
            else:
                if not _fits_token_budget(token_parts, line, max_tokens=max_tokens):
                    break
                facts.append(line)
            token_parts.append(line)

            if include_evidence:
                for evidence_line in _evidence_lines(memory):
                    if not _fits_token_budget(token_parts, evidence_line, max_tokens=max_tokens):
                        break
                    evidence_items.append(evidence_line)
                    token_parts.append(evidence_line)

        after_text = "\n".join([*preferences, *facts, *episodic_context, *evidence_items])
        return ContextPacket(
            request=request,
            classification=classification,
            preferences=preferences,
            facts=facts,
            episodic_context=episodic_context,
            evidence=evidence_items,
            before_token_estimate=_estimate_raw_tokens(memories),
            after_token_estimate=_estimate_tokens(after_text),
            token_budget=max_tokens,
        )

    def _search_relevant_memories(
        self,
        *,
        workspace: str | None,
        project: str | None,
        component: str | None,
        topic: str | None,
        include_global: bool,
        scope_path: Sequence[str] | None,
        include_inherited: bool,
        **search_kwargs: Any,
    ) -> list[MemorySearchResult]:
        if scope_path:
            scoped_search = getattr(self.retriever, "search_scope_path_memories", None)
            if callable(scoped_search):
                return scoped_search(
                    scope_path=scope_path,
                    include_inherited=include_inherited,
                    **search_kwargs,
                )
            search_kwargs = {
                **search_kwargs,
                "applies_to": {
                    **(search_kwargs.get("applies_to") or {}),
                    SCOPE_PATH_KEY: list(scope_path),
                },
            }
            return self.retriever.search_memories(**search_kwargs)

        if not workspace and not project and not component:
            return self.retriever.search_memories(**search_kwargs)

        hierarchical_search = getattr(self.retriever, "search_hierarchical_memories", None)
        if callable(hierarchical_search):
            return hierarchical_search(
                workspace=workspace,
                project=project,
                component=component,
                topic=topic,
                include_global=include_global,
                **search_kwargs,
            )

        layers = []
        if component:
            layers.append(
                with_memory_scope(
                    search_kwargs.get("applies_to"),
                    memory_scope=COMPONENT_MEMORY_SCOPE,
                    workspace=workspace,
                    project=project,
                    component=component,
                    topic=topic,
                )
            )
        if project:
            layers.append(
                with_memory_scope(
                    search_kwargs.get("applies_to"),
                    memory_scope=PROJECT_MEMORY_SCOPE,
                    workspace=workspace,
                    project=project,
                )
            )
        if workspace:
            layers.append(
                with_memory_scope(
                    without_applies_to_keys(
                        search_kwargs.get("applies_to"),
                        PROJECT_KEY,
                        COMPONENT_KEY,
                        TOPIC_KEY,
                    ),
                    memory_scope=WORKSPACE_MEMORY_SCOPE,
                    workspace=workspace,
                )
            )
        if include_global:
            layers.append(
                with_memory_scope(
                    without_applies_to_keys(
                        search_kwargs.get("applies_to"),
                        WORKSPACE_KEY,
                        PROJECT_KEY,
                        COMPONENT_KEY,
                        TOPIC_KEY,
                    ),
                    memory_scope=GLOBAL_MEMORY_SCOPE,
                )
            )

        results: list[MemorySearchResult] = []
        seen: set[Any] = set()
        for scoped_applies_to in layers:
            scoped_results = self.retriever.search_memories(
                **{
                    **search_kwargs,
                    "applies_to": scoped_applies_to,
                }
            )
            for result in scoped_results:
                memory_id = result.memory.id
                if memory_id in seen:
                    continue
                seen.add(memory_id)
                results.append(result)
                if len(results) >= search_kwargs["limit"]:
                    return results
        return results


def _memory_line(memory: Memory, *, include_detail: bool) -> str:
    summary = memory.summary or memory.content
    if include_detail and memory.summary and memory.content != memory.summary:
        return f"{summary} Detail: {memory.content}"
    return summary


def _packet_category(memory_type: str) -> str:
    if "preference" in memory_type:
        return "preferences"
    if memory_type in {"event", "episodic_note", "conversation", "ephemeral_note"}:
        return "episodic"
    return "facts"


def _evidence_lines(memory: Memory) -> list[str]:
    lines: list[str] = []
    for item in memory.evidence or []:
        if isinstance(item, dict):
            kind = item.get("kind", "evidence")
            text = item.get("text", "")
            source = item.get("source")
            suffix = f" Source: {source}" if source else ""
            lines.append(f"{memory.memory_type}: {kind}: {text}{suffix}".strip())
        else:
            lines.append(f"{memory.memory_type}: {item}")
    return lines


def _estimate_raw_tokens(memories: Sequence[Memory]) -> int:
    raw_parts: list[str] = []
    for memory in memories:
        raw_parts.extend(
            [
                memory.memory_type,
                memory.content or "",
                memory.summary or "",
                repr(memory.evidence or []),
                repr(memory.metadata_ or {}),
                repr(memory.applies_to or {}),
            ]
        )
    return _estimate_tokens("\n".join(raw_parts))


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _fits_token_budget(parts: Sequence[str], candidate: str, *, max_tokens: int | None) -> bool:
    if max_tokens is None:
        return True
    return _estimate_tokens("\n".join([*parts, candidate])) <= max_tokens


def _bullet_lines(items: Sequence[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _contains_any(text: str, words: Sequence[str]) -> bool:
    return any(word in text for word in words)


def _merge_scoped_results(
    project_results: Sequence[MemorySearchResult],
    global_results: Sequence[MemorySearchResult],
    *,
    limit: int,
) -> list[MemorySearchResult]:
    seen: set[Any] = set()
    ranked: list[tuple[int, float, float, MemorySearchResult]] = []

    for priority, results in ((1, project_results), (0, global_results)):
        for result in results:
            memory_id = result.memory.id
            if memory_id in seen:
                continue
            seen.add(memory_id)
            ranked.append((priority, result.rank_score, result.recency_score, result))

    ranked.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [item[3] for item in ranked[:limit]]
