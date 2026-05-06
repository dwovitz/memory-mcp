"""Synthesize compact LLM-ready context packets from memories."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy.orm import Session

from memory_mcp.embeddings.config import get_embedding_service
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
    REPO_KEY,
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


PROJECT_CONTEXT_REQUEST_TERMS = (
    "api",
    "app",
    "architecture",
    "architectural",
    "auth",
    "authorization",
    "backend",
    "code",
    "coding",
    "correctness",
    "database",
    "deployment",
    "endpoint",
    "frontend",
    "migration",
    "mcp",
    "performance",
    "persistence",
    "project",
    "python",
    "repo",
    "repository",
    "security",
    "service",
    "services",
    "test",
    "tests",
)
BROADER_PROJECT_CONTEXT_TERMS = (
    "architecture",
    "architectural",
    "correctness",
    "risk",
    "risks",
    "plan",
    "planning",
    "security",
    "authorization",
    "performance",
    "test",
    "tests",
    "validation",
)
WEAK_PROJECT_PACKET_TOKEN_THRESHOLD = 24
FOCUSED_VERIFICATION_BUDGET_TOKENS = 2_000
IMPLEMENTATION_SOURCE_BUDGET_TOKENS = 4_000
NO_SOURCE_READ_BUDGET_TOKENS = 0
SOURCE_READ_LIMITS_BY_POLICY = {
    "none": {
        "max_files_before_edit": 0,
        "max_snippets": 0,
        "max_lines_per_snippet": 0,
        "path_enum_allowed": False,
        "source_content_allowed": False,
        "broad_read_disallowed": True,
    },
    "path_enum_only": {
        "max_files_before_edit": 0,
        "max_snippets": 0,
        "max_lines_per_snippet": 0,
        "path_enum_allowed": True,
        "source_content_allowed": False,
        "broad_read_disallowed": True,
    },
    "focused_snippets": {
        "max_files_before_edit": 4,
        "max_snippets": 6,
        "max_lines_per_snippet": 40,
        "path_enum_allowed": True,
        "source_content_allowed": True,
        "broad_read_disallowed": True,
    },
    "implementation_required": {
        "max_files_before_edit": 8,
        "max_snippets": 10,
        "max_lines_per_snippet": 60,
        "path_enum_allowed": True,
        "source_content_allowed": True,
        "broad_read_disallowed": True,
    },
}
SOURCE_READ_OVER_BUDGET_EXCEPTION = (
    "Only exceed this budget after naming the missing fact, the file or symbol likely to contain it, "
    "and why the implementation or validation cannot proceed without that read."
)
FALLBACK_SEARCH_EXAMPLES = [
    "git grep -l <term>",
    "grep -R -l <term> <candidate-dirs>",
    "git ls-files with targeted filtering",
    "Select-String -List over known candidate files",
]
FALLBACK_SEARCH_DISALLOWED_EXAMPLES = [
    "git grep -n <term>",
    "git grep <term> without -l",
    "recursive grep without -l",
    "Select-String without -List for discovery",
    "Get-Content over many files",
]
DEGRADED_SEARCH_GUIDANCE = (
    "If fast search such as rg is unavailable, run path-only search first before reading snippets "
    "(for example: git grep -l <term>, grep -R -l <term> <candidate-dirs>, git ls-files with "
    "targeted filtering, or Select-String -List over known candidate files). Path-only commands "
    "are discovery-only: they identify candidate files, not source context to consume. Select-String "
    "-List is allowed only when listing matching files for discovery; Select-String output with "
    "matching source lines is source reading, not discovery. Broad recursive source-output dumps "
    "are disallowed as a substitute for search. If fallback search starts printing source lines, "
    "stop immediately, discard that output as search context, rerun path-only search, and count "
    "the incident as a budget failure when tracking benchmark source-read compliance. After "
    "path-only search, read only bounded snippets from selected files."
)
BOUNDED_SNIPPET_GUIDANCE = (
    "After discovery, read only bounded snippets from selected files. A bounded snippet should stay "
    "within the advertised max lines per snippet when that value is nonzero. If a command returns "
    "more source lines than the snippet limit, stop using that output, discard oversized snippet "
    "output, rerun a bounded read, and count the incident as a source-read budget failure when "
    "benchmark tracking asks."
)
BOUNDED_SNIPPET_COUNT_GUIDANCE = (
    "Bounded snippets still count toward source_read_limits.max_snippets. Staying under "
    "max_lines_per_snippet is not enough if max_snippets is exceeded. Before the first edit, inspect "
    "only the top few directly implicated files/snippets. Stop at source_read_limits.max_snippets "
    "before the first edit. If more snippets are needed before the first edit, name the missing fact, "
    "likely file/symbol, and why the current bounded snippets are insufficient before reading more. "
    "Exceeding max_snippets before first edit means source_read_budget_obeyed: no unless an explicit "
    "exception was recorded before exceeding it."
)
BOUNDED_SNIPPET_EXCEPTION_GUIDANCE = (
    "Before exceeding the snippet limit, name the missing fact, the likely file or symbol, and why "
    "that fact cannot be validated with a bounded snippet."
)
PRE_EDIT_SEQUENCE = [
    "enumerate likely paths",
    "choose the top candidate files",
    "read only bounded snippets from those candidates",
    "stop at the budget checkpoint before reading more",
    "make the first edit or explicitly record a budget exception",
]
PRE_EDIT_STOP_RULE = (
    "Stop at the pre-edit budget checkpoint before reading more source. If the likely edit surface "
    "is still unclear, make the first edit at the most likely boundary or explicitly record a budget "
    "exception before reading more files or snippets."
)
PRE_EDIT_EXPANSION_RULE = (
    "Reading additional files or snippets before the first edit requires naming the missing fact, "
    "the file or symbol likely to contain it, and why implementation cannot proceed without it. "
    "Unless a benchmark explicitly allows the exception, extra pre-edit reads count as a budget failure."
)
PRE_EDIT_DEFAULT_ACTION_RULE = (
    "At the pre-edit budget checkpoint, the default action is to make the first edit at the most likely "
    "boundary rather than continue reading to complete the full context map. A recorded exception explains "
    "budget failure; it does not preserve compliance."
)


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
    diagnostics: dict[str, Any] = field(default_factory=dict)

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
        context_quality = self.diagnostics.get("context_quality")
        if context_quality:
            sections.append(f"Context quality: {context_quality}")
        if self.preferences:
            sections.extend(["", "## Preferences", *_bullet_lines(self.preferences)])
        if self.facts:
            sections.extend(["", "## Facts", *_bullet_lines(self.facts)])
        if self.episodic_context:
            sections.extend(["", "## Episodic Context", *_bullet_lines(self.episodic_context)])
        if self.evidence:
            sections.extend(["", "## Evidence", *_bullet_lines(self.evidence)])
        warnings = self.diagnostics.get("warnings") or []
        if warnings:
            sections.extend(["", "## Warnings", *_bullet_lines(warnings)])
        source_guidance = _source_guidance_lines(self.diagnostics)
        if source_guidance:
            sections.extend(["", "## Source Read Guidance", *_bullet_lines(source_guidance)])
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
        self.retriever = retriever or HybridRetrievalService(session, embedding_service=get_embedding_service(session))  # type: ignore[arg-type]

    def classify_request(self, request: str) -> RequestClassification:
        normalized = request.lower()
        wants_detail = any(
            word in normalized
            for word in ("detail", "details", "evidence", "why", "exact", "dose", "dosage", "full")
        )

        if _looks_like_project_context_request(normalized) and _is_implementation_project_request(normalized):
            return RequestClassification(
                domain="project",
                memory_types=PROJECT_CONTEXT_MEMORY_TYPES,
                include_detail=wants_detail,
                rationale="Implementation requests with project terms need coding context even when they mention domain data.",
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
        if _looks_like_project_context_request(normalized):
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
        repo: str | None = None,
        project: str | None = None,
        component: str | None = None,
        topic: str | None = None,
        include_global: bool = True,
        scope_path: Sequence[str] | None = None,
        include_inherited: bool = True,
        max_tokens: int | None = None,
    ) -> ContextPacket:
        classification = self.classify_request(request)
        if classification.domain == "general" and (project or component or scope_path):
            classification = RequestClassification(
                domain="project",
                memory_types=PROJECT_CONTEXT_MEMORY_TYPES,
                include_detail=classification.include_detail,
                rationale="Explicit project scope indicates project context retrieval.",
            )
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
            repo=repo,
            project=project,
            component=component,
            topic=topic,
            include_global=include_global,
            scope_path=scope_path,
            include_inherited=include_inherited,
            **search_kwargs,
        )
        fallback_attempts: list[dict[str, Any]] = []
        fallback_reason = _component_fallback_reason(
            request,
            results,
            project=project,
            component=component,
        )
        if fallback_reason:
            fallback_results = self._search_relevant_memories(
                workspace=workspace,
                repo=repo,
                project=project,
                component=None,
                topic=None,
                include_global=include_global,
                scope_path=scope_path,
                include_inherited=include_inherited,
                **search_kwargs,
            )
            primary_first = fallback_reason == "broad_project_request" and _has_project_scoped_memory(
                [result.memory for result in results],
                project,
            )
            merged_results = _merge_unique_results(
                results if primary_first else fallback_results,
                fallback_results if primary_first else results,
                limit=max_memories,
            )
            fallback_attempts.append(
                {
                    "reason": fallback_reason,
                    "from_component": component,
                    "to_scope": "project",
                    "result_count": len(fallback_results),
                    "accepted": _result_ids(merged_results) != _result_ids(results),
                }
            )
            if fallback_attempts[-1]["accepted"]:
                results = merged_results
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
        after_token_estimate = _estimate_tokens(after_text)
        diagnostics = _packet_diagnostics(
            memories,
            request=request,
            project=project,
            component=component,
            fallback_attempts=fallback_attempts,
            after_token_estimate=after_token_estimate,
        )
        return ContextPacket(
            request=request,
            classification=classification,
            preferences=preferences,
            facts=facts,
            episodic_context=episodic_context,
            evidence=evidence_items,
            before_token_estimate=_estimate_raw_tokens(memories),
            after_token_estimate=after_token_estimate,
            token_budget=max_tokens,
            diagnostics=diagnostics,
        )

    def _search_relevant_memories(
        self,
        *,
        workspace: str | None,
        repo: str | None = None,
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
                repo=repo,
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
                    repo=repo,
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
                    repo=repo,
                    project=project,
                )
            )
        if workspace:
            layers.append(
                with_memory_scope(
                    without_applies_to_keys(
                        search_kwargs.get("applies_to"),
                        REPO_KEY,
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
                        REPO_KEY,
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


def _looks_like_project_context_request(text: str) -> bool:
    return _contains_any(text, PROJECT_CONTEXT_REQUEST_TERMS)


def _is_broad_project_context_request(text: str) -> bool:
    return _contains_any(text.lower(), BROADER_PROJECT_CONTEXT_TERMS)


def _component_fallback_reason(
    request: str,
    results: Sequence[MemorySearchResult],
    *,
    project: str | None,
    component: str | None,
) -> str | None:
    if not project or not component:
        return None
    if _is_broad_project_context_request(request):
        return "broad_project_request"
    memories = [result.memory for result in results]
    if not _has_project_scoped_memory(memories, project):
        return "weak_component_packet"
    if not _has_direct_component_memory(memories, project=project, component=component):
        return "missing_component_match"
    return None


def _packet_diagnostics(
    memories: Sequence[Memory],
    *,
    request: str,
    project: str | None,
    component: str | None,
    fallback_attempts: Sequence[dict[str, Any]],
    after_token_estimate: int,
) -> dict[str, Any]:
    warnings: list[str] = []
    has_project_scoped_facts = _has_project_scoped_memory(memories, project)
    has_component_scoped_facts = _has_any_component_memory(memories, project=project)
    has_direct_component_facts = _has_direct_component_memory(
        memories,
        project=project,
        component=component,
    )
    only_workspace_or_global = bool(memories) and not has_project_scoped_facts
    broad_project_request = _is_broad_project_context_request(request)
    implementation_request = _is_implementation_project_request(request)
    if not memories:
        warnings.append("No memories matched this request.")
    if project and not has_project_scoped_facts:
        warnings.append(
            f"No project-scoped memories matched project '{project}'; context may be incomplete."
        )
    if component and not has_direct_component_facts:
        warnings.append(
            f"No direct memories matched component '{component}'; project-scope fallback may be more reliable."
        )
    if project and after_token_estimate < WEAK_PROJECT_PACKET_TOKEN_THRESHOLD:
        warnings.append("Rendered packet is unusually small for a project request.")
    if any(attempt.get("accepted") for attempt in fallback_attempts):
        warnings.append("Fallback broadened retrieval from component scope to project scope.")

    context_quality = "strong"
    if not memories:
        context_quality = "miss"
    elif project and not has_project_scoped_facts:
        context_quality = "weak"
    elif project and after_token_estimate < WEAK_PROJECT_PACKET_TOKEN_THRESHOLD:
        context_quality = "weak"
    elif component and not has_direct_component_facts:
        context_quality = "usable"
    elif warnings:
        context_quality = "usable"

    source_read_policy, suggested_next_action, source_read_budget_tokens = _source_read_decision(
        context_quality=context_quality,
        broad_project_request=broad_project_request,
        implementation_request=implementation_request,
    )
    source_read_limits = _source_read_limits(
        source_read_policy,
        source_read_budget_tokens=source_read_budget_tokens,
    )
    source_read_contract = _source_read_contract(
        source_read_policy=source_read_policy,
        suggested_next_action=suggested_next_action,
        source_read_budget_tokens=source_read_budget_tokens,
        limits=source_read_limits,
    )

    return {
        "context_quality": context_quality,
        "warnings": warnings,
        "fallback_attempts": list(fallback_attempts),
        "matched_scopes": _unique_ordered(_format_memory_scope(memory) for memory in memories),
        "matched_memory_types": _unique_ordered(memory.memory_type for memory in memories),
        "matched_scope_counts": _counts(_format_memory_scope(memory) for memory in memories),
        "matched_memory_type_counts": _counts(memory.memory_type for memory in memories),
        "has_project_scoped_facts": has_project_scoped_facts,
        "has_component_scoped_facts": has_component_scoped_facts,
        "has_direct_component_facts": has_direct_component_facts,
        "only_workspace_or_global_facts": only_workspace_or_global,
        "broad_project_request": broad_project_request,
        "implementation_request": implementation_request,
        "suggested_next_action": suggested_next_action,
        "source_read_policy": source_read_policy,
        "source_read_budget_tokens": source_read_budget_tokens,
        "source_read_limits": source_read_limits,
        "source_read_contract": source_read_contract,
        "verification_focus": _verification_focus_examples(request),
    }


def _has_project_scoped_memory(memories: Sequence[Memory], project: str | None) -> bool:
    if not project:
        return False
    for memory in memories:
        applies_to = memory.applies_to or {}
        if applies_to.get(PROJECT_KEY) == project and applies_to.get("memory_scope") in {
            PROJECT_MEMORY_SCOPE,
            COMPONENT_MEMORY_SCOPE,
        }:
            return True
        scope_path = applies_to.get(SCOPE_PATH_KEY)
        if isinstance(scope_path, Sequence) and not isinstance(scope_path, str):
            if f"project:{project}" in {str(part) for part in scope_path}:
                return True
    return False


def _has_direct_component_memory(
    memories: Sequence[Memory],
    *,
    project: str | None,
    component: str | None,
) -> bool:
    if not component:
        return False
    for memory in memories:
        applies_to = memory.applies_to or {}
        if applies_to.get("memory_scope") != COMPONENT_MEMORY_SCOPE:
            continue
        if applies_to.get(COMPONENT_KEY) != component:
            continue
        if project and applies_to.get(PROJECT_KEY) != project:
            continue
        return True
    return False


def _has_any_component_memory(
    memories: Sequence[Memory],
    *,
    project: str | None,
) -> bool:
    for memory in memories:
        applies_to = memory.applies_to or {}
        if applies_to.get("memory_scope") != COMPONENT_MEMORY_SCOPE:
            continue
        if project and applies_to.get(PROJECT_KEY) != project:
            continue
        return True
    return False


def _format_memory_scope(memory: Memory) -> str:
    applies_to = memory.applies_to or {}
    memory_scope = applies_to.get("memory_scope")
    if memory_scope == COMPONENT_MEMORY_SCOPE:
        project = applies_to.get(PROJECT_KEY, "*")
        component = applies_to.get(COMPONENT_KEY, "*")
        return f"component:{project}/{component}"
    if memory_scope == PROJECT_MEMORY_SCOPE:
        return f"project:{applies_to.get(PROJECT_KEY, '*')}"
    if memory_scope == WORKSPACE_MEMORY_SCOPE:
        return f"workspace:{applies_to.get(WORKSPACE_KEY, '*')}"
    if memory_scope == GLOBAL_MEMORY_SCOPE:
        return "global"
    if SCOPE_PATH_KEY in applies_to:
        return "scope_path:" + "/".join(str(part) for part in applies_to[SCOPE_PATH_KEY])
    return "unscoped"


def _unique_ordered(items: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _counts(items: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def _merge_unique_results(
    primary: Sequence[MemorySearchResult],
    secondary: Sequence[MemorySearchResult],
    *,
    limit: int,
) -> list[MemorySearchResult]:
    seen: set[Any] = set()
    merged: list[MemorySearchResult] = []
    for result in (*primary, *secondary):
        memory_id = result.memory.id
        if memory_id in seen:
            continue
        seen.add(memory_id)
        merged.append(result)
        if len(merged) >= limit:
            break
    return merged


def _result_ids(results: Sequence[MemorySearchResult]) -> list[Any]:
    return [result.memory.id for result in results]


def _is_implementation_project_request(text: str) -> bool:
    return _contains_any(
        text.lower(),
        (
            "add",
            "change",
            "changing",
            "edit",
            "editing",
            "fix",
            "implement",
            "implementation",
            "modify",
            "modifying",
            "patch",
            "refactor",
        ),
    )


def _source_read_decision(
    *,
    context_quality: str,
    broad_project_request: bool,
    implementation_request: bool,
) -> tuple[str, str, int]:
    if context_quality in {"miss", "weak"}:
        return "none", "mark_weak_context", NO_SOURCE_READ_BUDGET_TOKENS
    if implementation_request and context_quality == "strong":
        return "implementation_required", "inspect_budget_then_edit", IMPLEMENTATION_SOURCE_BUDGET_TOKENS
    if broad_project_request:
        if context_quality == "strong":
            return "path_enum_only", "answer_from_packet", NO_SOURCE_READ_BUDGET_TOKENS
        return "focused_snippets", "verify_narrowly", FOCUSED_VERIFICATION_BUDGET_TOKENS
    if implementation_request:
        return "implementation_required", "inspect_budget_then_edit", IMPLEMENTATION_SOURCE_BUDGET_TOKENS
    if context_quality == "usable":
        return "focused_snippets", "verify_narrowly", FOCUSED_VERIFICATION_BUDGET_TOKENS
    return "path_enum_only", "answer_from_packet", NO_SOURCE_READ_BUDGET_TOKENS


def _source_read_limits(
    source_read_policy: str,
    *,
    source_read_budget_tokens: int,
) -> dict[str, Any]:
    limits = dict(SOURCE_READ_LIMITS_BY_POLICY.get(source_read_policy, SOURCE_READ_LIMITS_BY_POLICY["none"]))
    limits["source_read_budget_tokens"] = source_read_budget_tokens
    limits["degraded_search_guidance"] = DEGRADED_SEARCH_GUIDANCE
    limits["path_only_search_first"] = True
    limits["broad_fallback_search_disallowed"] = True
    limits["fallback_search_examples"] = list(FALLBACK_SEARCH_EXAMPLES)
    limits["fallback_search_disallowed_examples"] = list(FALLBACK_SEARCH_DISALLOWED_EXAMPLES)
    limits["stop_on_source_output_fallback"] = True
    limits["fallback_source_output_counts_as_budget_failure"] = True
    limits["path_only_discovery_only"] = True
    limits["select_string_list_only_for_discovery"] = True
    limits["bounded_snippets_after_discovery"] = True
    limits["oversized_snippet_counts_as_budget_failure"] = True
    limits["discard_oversized_snippet_output"] = True
    limits["snippet_count_limit_is_hard"] = True
    limits["bounded_snippets_still_count_toward_budget"] = True
    limits["stop_at_max_snippets_before_edit"] = True
    limits["exceeding_snippet_count_counts_as_budget_failure"] = True
    limits["over_budget_exception"] = SOURCE_READ_OVER_BUDGET_EXCEPTION
    if source_read_policy == "implementation_required":
        limits["pre_edit_path_discovery_required"] = True
        limits["pre_edit_candidate_selection_required"] = True
        limits["pre_edit_budget_checkpoint_required"] = True
        limits["extra_pre_edit_reads_require_exception"] = True
        limits["extra_pre_edit_reads_count_as_budget_failure"] = True
        limits["pre_edit_checkpoint_default_action"] = "make_first_edit"
        limits["pre_edit_exception_preserves_budget_compliance"] = False
        limits["pre_edit_sequence"] = list(PRE_EDIT_SEQUENCE)
        limits["pre_edit_stop_rule"] = PRE_EDIT_STOP_RULE
        limits["pre_edit_expansion_rule"] = PRE_EDIT_EXPANSION_RULE
        limits["pre_edit_default_action_rule"] = PRE_EDIT_DEFAULT_ACTION_RULE
    return limits


def _source_read_contract(
    *,
    source_read_policy: str,
    suggested_next_action: str,
    source_read_budget_tokens: int,
    limits: dict[str, Any],
) -> dict[str, Any]:
    """Return a compact source-read contract for client skills and hooks."""

    return {
        "version": "source-read-contract/v1",
        "source_read_policy": source_read_policy,
        "suggested_next_action": suggested_next_action,
        "source_read_budget_tokens": source_read_budget_tokens,
        "pre_edit_limits": {
            "max_files": limits.get("max_files_before_edit", 0),
            "max_snippets": limits.get("max_snippets", 0),
            "max_lines_per_snippet": limits.get("max_lines_per_snippet", 0),
        },
        "allowed_discovery": list(limits.get("fallback_search_examples") or []),
        "disallowed_discovery": list(limits.get("fallback_search_disallowed_examples") or []),
        "counting_rules": {
            "bounded_snippets_count_toward_max_snippets": bool(
                limits.get("bounded_snippets_still_count_toward_budget")
            ),
            "path_only_discovery_counts_as_source_read": False,
            "select_string_list_is_path_only_discovery": bool(
                limits.get("select_string_list_only_for_discovery")
            ),
            "select_string_matches_count_as_snippets": bool(
                limits.get("select_string_list_only_for_discovery")
            ),
            "fallback_source_output_counts_as_budget_failure": bool(
                limits.get("fallback_source_output_counts_as_budget_failure")
            ),
            "oversized_snippet_counts_as_budget_failure": bool(
                limits.get("oversized_snippet_counts_as_budget_failure")
            ),
            "exceeding_max_snippets_counts_as_budget_failure": bool(
                limits.get("exceeding_snippet_count_counts_as_budget_failure")
            ),
        },
        "pre_edit_checkpoint": {
            "required": bool(limits.get("pre_edit_budget_checkpoint_required")),
            "stop_at_max_snippets": bool(limits.get("stop_at_max_snippets_before_edit")),
            "default_action": limits.get("pre_edit_checkpoint_default_action", "answer_or_verify"),
        },
        "exception_rule": {
            "required_before_exceeding_budget": True,
            "preserves_budget_compliance": bool(
                limits.get("pre_edit_exception_preserves_budget_compliance", False)
            ),
            "must_name": [
                "missing_fact",
                "likely_file_or_symbol",
                "why_current_bounded_snippets_are_insufficient",
            ],
        },
        "failure_conditions": [
            "source_content_read_when_source_content_allowed == false",
            "pre_edit_source_files_read_count > pre_edit_limits.max_files",
            "pre_edit_source_snippets_read_count > pre_edit_limits.max_snippets",
            "snippet_line_count > pre_edit_limits.max_lines_per_snippet",
            "max_snippet_lines_obeyed == false",
            "fallback_search_mode == content_dump",
            "exception_recorded_after_budget_exceeded",
        ],
        "reporting_fields": [
            "source_read_budget_obeyed",
            "source_files_read_count",
            "source_snippets_read_count",
            "pre_edit_source_files_read_count",
            "pre_edit_source_snippets_read_count",
            "max_snippet_lines_obeyed",
            "source_budget_exception",
            "fallback_search_mode",
            "fallback_search_commands",
            "broad_search_output_stopped",
        ],
    }


def _verification_focus_examples(request: str) -> list[str]:
    text = request.lower()
    if _contains_any(text, ("test", "tests", "validation")):
        return [
            "test path names",
            "fixture or helper signatures",
            "small assertion excerpts from one or two targeted tests",
        ]
    if _contains_any(text, ("auth", "authorization", "security", "endpoint", "backend", "api")):
        return [
            "route or endpoint definitions",
            "auth middleware and permission checks",
            "small service/model contract snippets",
        ]
    if _contains_any(text, ("architecture", "risk", "risks", "performance")):
        return [
            "module path enumeration",
            "public interfaces for implicated services",
            "small excerpts around documented boundaries",
        ]
    return [
        "path enumeration",
        "small excerpts from the directly implicated files",
    ]


def _source_guidance_lines(diagnostics: dict[str, Any]) -> list[str]:
    suggested_next_action = diagnostics.get("suggested_next_action")
    source_read_policy = diagnostics.get("source_read_policy")
    if not suggested_next_action or not source_read_policy:
        return []
    lines = [
        f"Suggested next action: {suggested_next_action}.",
        f"Source read policy: {source_read_policy}.",
        f"Recommended post-packet source budget: {diagnostics.get('source_read_budget_tokens', 0)} tokens.",
    ]
    limits = diagnostics.get("source_read_limits") or {}
    if limits:
        lines.append(
            "Source read limits: "
            f"max files before edit {limits.get('max_files_before_edit', 0)}, "
            f"max snippets {limits.get('max_snippets', 0)}, "
            f"max lines per snippet {limits.get('max_lines_per_snippet', 0)}, "
            f"path enumeration allowed {str(limits.get('path_enum_allowed', False)).lower()}, "
            f"broad reads disallowed {str(limits.get('broad_read_disallowed', True)).lower()}."
        )
        if source_read_policy == "implementation_required":
            lines.append(
                "Implementation workflow: enumerate likely paths, run path-only search first, choose "
                "the top candidate files, read only bounded snippets from those candidates, stop at "
                "the budget checkpoint before reading more, then make the first edit or explicitly "
                "record a budget exception."
            )
            lines.append(
                "Before the first edit, extra pre-edit reads require a recorded budget exception: "
                "name the missing fact and likely file or symbol before expanding. Unless the "
                "benchmark explicitly allows it, those extra reads count as a budget failure."
            )
            lines.append(PRE_EDIT_DEFAULT_ACTION_RULE)
            lines.append(
                "Do not read tests, model, route, presenter, policy, migration, and client files all "
                "up front. Pick the most likely entry point and one or two directly adjacent boundaries "
                "first; expand only after the first edit or after recording the exception."
            )
            lines.append(
                "Snippet size limits are hard pre-edit limits. Do not read oversized chunks and later "
                "describe them as bounded."
            )
        if limits.get("path_only_discovery_only"):
            lines.append(
                "Path-only commands are discovery-only. They identify candidate files, not source "
                "context to consume."
            )
        if limits.get("select_string_list_only_for_discovery"):
            lines.append(
                "Select-String -List is allowed only when listing matching files for discovery; "
                "Select-String output with matching source lines is a source snippet read."
            )
        guidance = limits.get("degraded_search_guidance")
        if guidance:
            lines.append(str(guidance))
        if limits.get("bounded_snippets_after_discovery"):
            lines.append(BOUNDED_SNIPPET_GUIDANCE)
        if limits.get("bounded_snippets_still_count_toward_budget"):
            lines.append(BOUNDED_SNIPPET_COUNT_GUIDANCE)
        if limits.get("oversized_snippet_counts_as_budget_failure"):
            lines.append(BOUNDED_SNIPPET_EXCEPTION_GUIDANCE)
        examples = limits.get("fallback_search_examples") or []
        if examples:
            lines.append("Fallback search examples: " + "; ".join(str(item) for item in examples) + ".")
        disallowed_examples = limits.get("fallback_search_disallowed_examples") or []
        if disallowed_examples:
            lines.append(
                "Disallowed fallback examples: "
                + "; ".join(str(item) for item in disallowed_examples)
                + "."
            )
        if limits.get("stop_on_source_output_fallback"):
            lines.append(
                "If fallback search starts printing source lines, stop immediately, discard that output, "
                "rerun path-only search, and count it as a budget failure when benchmarks ask."
            )
        exception = limits.get("over_budget_exception")
        if exception:
            lines.append(str(exception))
    focus = diagnostics.get("verification_focus") or []
    if focus and source_read_policy in {"focused_snippets", "implementation_required"}:
        lines.append("Verification focus: " + "; ".join(str(item) for item in focus) + ".")
    return lines


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
