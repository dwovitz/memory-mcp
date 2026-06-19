"""Projection-aware retrieval over semantic chunks and the wiki entity graph.

This is the unified retrieval entry point for issue MMCP-28. It combines the
existing structured/lexical/semantic ranking from
:class:`~memory_mcp.retrieval.service.HybridRetrievalService` with **bounded
relationship expansion** over the wiki-derived entity graph, and annotates every
returned item with *why* it was retrieved plus its source provenance.

Design goals:

* Combine signals — lexical + semantic + structured filters + recency +
  confidence (delegated to the hybrid retriever) and relationship expansion
  (added here).
* Bound expansion — by graph depth, expanded-result count, sensitivity, and a
  context token budget, so a packet can never grow without limit.
* Explain retrieval — each item carries human-readable ``reasons`` and the
  ``metadata.source`` provenance block, so packets are auditable.
* Keep exact lookup — deterministic reference resolution by ``ingest_key`` or by
  canonical wiki source location stays available alongside fuzzy recall.

The service depends only on small ports (a memory retriever, a relationship
neighbor source, and a memory lookup), so it is fully unit-testable without a
database.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

# Default sensitivities for projection retrieval. Wiki-derived content is
# private by default, so relationship expansion that should surface wiki context
# must be asked for explicitly via ``sensitivities``.
DEFAULT_SENSITIVITIES: tuple[str, ...] = ("normal",)

# Reason tags attached to retrieved items (stable strings for clients to group).
REASON_PRIMARY_MATCH = "primary_match"
REASON_RELATIONSHIP_EXPANSION = "relationship_expansion"
REASON_EXACT_LOOKUP = "exact_lookup"


class _MemoryLike(Protocol):
    id: UUID
    content: str
    entity_id: UUID | None
    sensitivity: str
    metadata_: dict[str, Any]
    confidence: Any


class _SearchResultLike(Protocol):
    memory: _MemoryLike
    rank_score: float


class _RelationshipLike(Protocol):
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str
    sensitivity: str
    description: str | None


class _Retriever(Protocol):
    def search_memories(self, **kwargs: Any) -> list[Any]: ...


class _NeighborSource(Protocol):
    def neighbors(
        self,
        entity_id: UUID,
        relationship_types: tuple[str, ...] | None = ...,
        direction: str = ...,
    ) -> list[Any]: ...


class _MemoryLookup(Protocol):
    def find_active_by_metadata_key(self, field: str, value: str) -> Any | None: ...

    def find_active_wiki_by_source(
        self, *, collection: str, path: str, section: str | None = ...
    ) -> Any | None: ...


@dataclass(frozen=True)
class RetrievedItem:
    """One retrieved memory plus the reasons it was selected."""

    memory: Any
    score: float
    reasons: list[str] = field(default_factory=list)
    provenance: dict[str, Any] | None = None
    depth: int = 0
    via_relationship: str | None = None

    def reason_summary(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "unspecified"


@dataclass(frozen=True)
class ProjectionRetrievalResult:
    """Bounded, provenance-backed retrieval output with diagnostics."""

    items: list[RetrievedItem] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _provenance_of(memory: Any) -> dict[str, Any] | None:
    metadata = getattr(memory, "metadata_", None) or {}
    source = metadata.get("source")
    return source if isinstance(source, dict) else None


class ProjectionRetrievalService:
    """Combine ranked search with bounded, explained relationship expansion."""

    def __init__(
        self,
        retriever: _Retriever,
        relationships: _NeighborSource,
        memories: _MemoryLookup,
    ) -> None:
        self._retriever = retriever
        self._relationships = relationships
        self._memories = memories

    def lookup_exact(
        self,
        *,
        ingest_key: str | None = None,
        collection: str | None = None,
        path: str | None = None,
        section: str | None = None,
        sensitivities: Sequence[str] | None = None,
    ) -> RetrievedItem | None:
        """Deterministically resolve a single projection by canonical reference.

        Resolves by projection ``ingest_key`` when given, otherwise by canonical
        wiki source location (``collection`` + ``path`` [+ ``section``]). Returns
        ``None`` if nothing matches or the match is filtered out by sensitivity.
        """
        memory: Any | None = None
        if ingest_key:
            memory = self._memories.find_active_by_metadata_key("ingest_key", ingest_key)
        elif collection and path:
            memory = self._memories.find_active_wiki_by_source(
                collection=collection, path=path, section=section
            )
        if memory is None:
            return None
        if sensitivities is not None and getattr(memory, "sensitivity", "normal") not in set(
            sensitivities
        ):
            return None
        return RetrievedItem(
            memory=memory,
            score=1.0,
            reasons=[REASON_EXACT_LOOKUP],
            provenance=_provenance_of(memory),
            depth=0,
        )

    def retrieve(
        self,
        *,
        text_query: str | None = None,
        memory_types: Sequence[str] | None = None,
        applies_to: dict[str, Any] | None = None,
        scope: str | None = None,
        tags: Sequence[str] | None = None,
        min_confidence: Any | None = None,
        sensitivities: Sequence[str] | None = None,
        limit: int = 10,
        expand_relationships: bool = True,
        relationship_types: Sequence[str] | None = None,
        max_depth: int = 1,
        max_expanded: int = 10,
        per_neighbor_limit: int = 3,
        max_tokens: int | None = None,
        exact_ref: dict[str, Any] | None = None,
    ) -> ProjectionRetrievalResult:
        """Retrieve a bounded, explained set of projections for a request.

        Args:
            text_query: Free-text query; drives lexical + semantic ranking.
            memory_types/applies_to/scope/tags/min_confidence: structured filters
                forwarded to the hybrid retriever.
            sensitivities: Allowed sensitivity labels. Bounds both the primary
                search and relationship expansion (defaults to ``('normal',)``).
            limit: Max primary (depth-0) results.
            expand_relationships: Whether to expand over the entity graph.
            relationship_types: Restrict expansion to these edge types.
            max_depth: Max graph hops from a primary result.
            max_expanded: Max expanded (depth>0) items added.
            per_neighbor_limit: Max memories pulled per neighbor entity.
            max_tokens: Optional context budget; stops adding items when the
                estimated rendered size would exceed it.
            exact_ref: Optional deterministic reference (``ingest_key`` or
                ``collection``/``path``/``section``) surfaced first.

        Returns:
            A :class:`ProjectionRetrievalResult` whose items each explain why they
            were retrieved and carry source provenance.
        """
        allowed = tuple(sensitivities) if sensitivities is not None else DEFAULT_SENSITIVITIES
        allowed_set = set(allowed)
        signals_used: list[str] = ["structured"]
        if text_query:
            signals_used.extend(["lexical", "semantic"])
        signals_used.extend(["recency", "confidence"])

        items: list[RetrievedItem] = []
        seen_memory_ids: set[Any] = set()
        used_tokens = 0
        budget_truncated = False

        def _try_add(item: RetrievedItem) -> bool:
            nonlocal used_tokens, budget_truncated
            mem_id = getattr(item.memory, "id", None)
            if mem_id in seen_memory_ids:
                return False
            cost = _estimate_tokens(getattr(item.memory, "content", "") or "")
            if max_tokens is not None and used_tokens + cost > max_tokens and items:
                budget_truncated = True
                return False
            items.append(item)
            seen_memory_ids.add(mem_id)
            used_tokens += cost
            return True

        # 0) Exact deterministic reference, surfaced first.
        exact_hit = False
        if exact_ref:
            exact_item = self.lookup_exact(sensitivities=allowed, **exact_ref)
            if exact_item is not None and _try_add(exact_item):
                signals_used.append("exact")
                exact_hit = True

        # 1) Primary ranked search (lexical + semantic + structured + recency + confidence).
        primary = self._retriever.search_memories(
            text_query=text_query,
            memory_types=tuple(memory_types) if memory_types else None,
            tags=tuple(tags) if tags else None,
            applies_to=applies_to,
            scope=scope,
            sensitivities=allowed,
            min_confidence=min_confidence,
            statuses=("active",),
            limit=limit,
        )
        seed_entities: list[UUID] = []
        for result in primary:
            memory = getattr(result, "memory", result)
            item = RetrievedItem(
                memory=memory,
                score=float(getattr(result, "rank_score", 0.0) or 0.0),
                reasons=[REASON_PRIMARY_MATCH],
                provenance=_provenance_of(memory),
                depth=0,
            )
            if _try_add(item):
                entity_id = getattr(memory, "entity_id", None)
                if entity_id is not None:
                    seed_entities.append(entity_id)

        # 2) Bounded relationship expansion over the wiki entity graph.
        expanded_count = 0
        depth_reached = 0
        rel_types = tuple(relationship_types) if relationship_types else None
        if expand_relationships and seed_entities and max_depth > 0:
            visited: set[UUID] = set(seed_entities)
            frontier: list[tuple[UUID, int]] = [(eid, 0) for eid in seed_entities]
            while frontier and expanded_count < max_expanded and not budget_truncated:
                entity_id, depth = frontier.pop(0)
                if depth >= max_depth:
                    continue
                for rel in self._relationships.neighbors(entity_id, rel_types, "both"):
                    if expanded_count >= max_expanded or budget_truncated:
                        break
                    if getattr(rel, "sensitivity", "normal") not in allowed_set:
                        continue
                    neighbor = _other_endpoint(rel, entity_id)
                    if neighbor is None or neighbor in visited:
                        continue
                    visited.add(neighbor)
                    neighbor_memories = self._retriever.search_memories(
                        entity_id=neighbor,
                        sensitivities=allowed,
                        statuses=("active",),
                        limit=per_neighbor_limit,
                    )
                    next_depth = depth + 1
                    added_any = False
                    for nresult in neighbor_memories:
                        if expanded_count >= max_expanded or budget_truncated:
                            break
                        nmemory = getattr(nresult, "memory", nresult)
                        rel_type = getattr(rel, "relationship_type", "related")
                        item = RetrievedItem(
                            memory=nmemory,
                            score=max(0.0, 1.0 - 0.25 * next_depth),
                            reasons=[
                                f"{REASON_RELATIONSHIP_EXPANSION}:{rel_type}@depth{next_depth}"
                            ],
                            provenance=_provenance_of(nmemory),
                            depth=next_depth,
                            via_relationship=rel_type,
                        )
                        if _try_add(item):
                            expanded_count += 1
                            added_any = True
                            depth_reached = max(depth_reached, next_depth)
                    if added_any and next_depth < max_depth:
                        frontier.append((neighbor, next_depth))

        if "expansion" not in signals_used and expanded_count:
            signals_used.append("expansion")

        diagnostics = {
            "signals_used": signals_used,
            "primary_count": sum(1 for i in items if i.depth == 0 and REASON_PRIMARY_MATCH in i.reasons),
            "expanded_count": expanded_count,
            "exact_hit": exact_hit,
            "total_items": len(items),
            "estimated_tokens": used_tokens,
            "token_budget": max_tokens,
            "budget_truncated": budget_truncated,
            "expansion_bounds": {
                "max_depth": max_depth,
                "max_expanded": max_expanded,
                "depth_reached": depth_reached,
                "expand_relationships": expand_relationships,
            },
            "allowed_sensitivities": list(allowed),
            "why_retrieved": [
                {
                    "memory_id": str(getattr(item.memory, "id", "")),
                    "depth": item.depth,
                    "reasons": item.reasons,
                    "provenance": item.provenance,
                }
                for item in items
            ],
        }
        return ProjectionRetrievalResult(items=items, diagnostics=diagnostics)


def _other_endpoint(rel: Any, entity_id: UUID) -> UUID | None:
    source = getattr(rel, "source_entity_id", None)
    target = getattr(rel, "target_entity_id", None)
    if source == entity_id:
        return target
    if target == entity_id:
        return source
    return None
