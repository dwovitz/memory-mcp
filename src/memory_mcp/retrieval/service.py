"""Hybrid retrieval service for structured memory data."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import math
import logging
import re
from typing import Any, TYPE_CHECKING

logger = logging.getLogger(__name__)
from uuid import UUID

if TYPE_CHECKING:
    from memory_mcp.embeddings.service import EmbeddingService

from sqlalchemy import Float, Select, case, cast, func, literal, literal_column, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, aliased

from memory_mcp.models import Entity, Memory, MemoryTag, Relationship
from memory_mcp.scopes import (
    COMPONENT_KEY,
    COMPONENT_MEMORY_SCOPE,
    GLOBAL_MEMORY_SCOPE,
    OVERRIDES_MEMORY_IDS_KEY,
    PROJECT_KEY,
    PROJECT_MEMORY_SCOPE,
    REPO_KEY,
    SCOPE_PATH_KEY,
    VALID_FROM_KEY,
    VALID_TO_KEY,
    TOPIC_KEY,
    WORKSPACE_KEY,
    WORKSPACE_MEMORY_SCOPE,
    scope_path_layers,
    with_memory_scope,
    without_applies_to_keys,
)


@dataclass(frozen=True)
class MemorySearchResult:
    """Ranked memory search result."""

    memory: Memory
    rank_score: float
    text_rank: float
    recency_score: float


@dataclass(frozen=True)
class EntitySearchResult:
    """Ranked entity search result."""

    entity: Entity
    rank_score: float


@dataclass(frozen=True)
class VectorSearchPlan:
    """Scaffold describing future vector search inputs."""

    status: str
    reason: str
    embedding_dimensions: int | None = None
    distance_metric: str = "cosine"
    preferred_index: str = "hnsw"


PROJECT_CONTEXT_MEMORY_TYPES = (
    "project_fact",
    "app_knowledge",
    "coding_preference",
    "dependency",
    "project_rule",
    "workflow_location",
    "component_summary",
    "architecture_decision",
    "external_reference",
)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class HybridRetrievalService:
    """Search and profile helpers built from structured filters and full text."""

    def __init__(self, session: Session, embedding_service: "EmbeddingService | None" = None) -> None:
        self.session = session
        self.embedding_service = embedding_service

    def search_memories(
        self,
        *,
        text_query: str | None = None,
        entity_id: UUID | None = None,
        memory_types: Sequence[str] | None = None,
        statuses: Sequence[str] | None = ("active",),
        sensitivities: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        applies_to: dict[str, Any] | None = None,
        scope: str | None = None,
        scope_path: Sequence[str] | None = None,
        min_confidence: Decimal | str | float | None = None,
        since: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
        query_embedding: Sequence[float] | None = None,
        cited_path: str | None = None,
    ) -> list[MemorySearchResult]:
        use_vector_rerank = (
            self.embedding_service is not None
            and text_query
            and query_embedding is None
        )
        candidate_limit = max(limit * 5, 50) if use_vector_rerank else limit

        statement = self.build_search_memories_statement(
            text_query=text_query,
            entity_id=entity_id,
            memory_types=memory_types,
            statuses=statuses,
            sensitivities=sensitivities,
            tags=tags,
            metadata_filter=metadata_filter,
            applies_to=applies_to,
            scope=scope,
            scope_path=scope_path,
            min_confidence=min_confidence,
            since=since,
            limit=candidate_limit,
            offset=offset if not use_vector_rerank else 0,
            cited_path=cited_path,
        )
        rows = self.session.execute(statement).all()
        candidates = [
            MemorySearchResult(
                memory=row[0],
                rank_score=float(row.rank_score or 0),
                text_rank=float(row.text_rank or 0),
                recency_score=float(row.recency_score or 0),
            )
            for row in rows
        ]

        if use_vector_rerank:
            try:
                q_emb: list[float] = self.embedding_service.provider.embed_texts([text_query])[0]
                blended: list[tuple[float, MemorySearchResult]] = []
                for result in candidates:
                    mem_emb = result.memory.embedding
                    if mem_emb is not None:
                        csim = cosine_similarity(list(q_emb), list(mem_emb))
                    else:
                        csim = 0.0
                    confidence = float(result.memory.confidence or 0.5)
                    score = (
                        0.35 * csim
                        + 0.35 * result.text_rank
                        + 0.2 * confidence
                        + 0.1 * result.recency_score
                    )
                    blended.append((score, result))
                blended.sort(key=lambda t: t[0], reverse=True)
                return [
                    MemorySearchResult(
                        memory=r.memory,
                        rank_score=s,
                        text_rank=r.text_rank,
                        recency_score=r.recency_score,
                    )
                    for s, r in blended[offset : offset + limit]
                ]
            except Exception:
                logger.warning("Vector re-ranking failed, falling back to FTS order", exc_info=True)

        return candidates[:limit]

    def build_search_memories_statement(
        self,
        *,
        text_query: str | None = None,
        entity_id: UUID | None = None,
        memory_types: Sequence[str] | None = None,
        statuses: Sequence[str] | None = ("active",),
        sensitivities: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        applies_to: dict[str, Any] | None = None,
        scope: str | None = None,
        scope_path: Sequence[str] | None = None,
        min_confidence: Decimal | str | float | None = None,
        since: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
        cited_path: str | None = None,
    ) -> Select[Any]:
        text_rank = _memory_text_rank(text_query)
        recency_score = _recency_score(Memory.created_at)
        rank_score = (
            (text_rank * literal(4.0))
            + (cast(Memory.confidence, Float) * literal(2.0))
            + recency_score
        ).label("rank_score")

        statement = select(
            Memory,
            rank_score,
            text_rank.label("text_rank"),
            recency_score.label("recency_score"),
        )

        if tags:
            statement = statement.join(MemoryTag, MemoryTag.memory_id == Memory.id).where(
                MemoryTag.tag.in_(list(tags)),
                MemoryTag.status == "active",
            )
        if text_query:
            statement = statement.where(_memory_search_vector().op("@@")(_plain_text_query(text_query)))
        if entity_id is not None:
            statement = statement.where(Memory.entity_id == entity_id)
        if memory_types:
            statement = statement.where(Memory.memory_type.in_(list(memory_types)))
        if statuses:
            statement = statement.where(Memory.status.in_(list(statuses)))
        if sensitivities:
            statement = statement.where(Memory.sensitivity.in_(list(sensitivities)))
        if metadata_filter:
            statement = statement.where(Memory.metadata_.contains(metadata_filter))
        if applies_to:
            statement = statement.where(Memory.applies_to.contains(applies_to))
        if scope:
            statement = statement.where(Memory.applies_to.contains({"scope": scope}))
        if scope_path:
            statement = statement.where(Memory.applies_to[SCOPE_PATH_KEY] == cast(list(scope_path), JSONB))
        if min_confidence is not None:
            statement = statement.where(Memory.confidence >= _decimal_value(min_confidence))
        if since is not None:
            statement = statement.where(Memory.created_at >= since)
        if cited_path:
            path_expr = f'$[*] ? (@.path starts with "{cited_path}")'
            statement = statement.where(
                func.jsonb_path_exists(Memory.code_citations, literal(path_expr))
            )

        return (
            statement.order_by(rank_score.desc(), Memory.created_at.desc(), Memory.id)
            .limit(limit)
            .offset(offset)
        )

    def search_entities(
        self,
        *,
        text_query: str | None = None,
        entity_types: Sequence[str] | None = None,
        statuses: Sequence[str] | None = ("active",),
        applies_to: dict[str, Any] | None = None,
        scope: str | None = None,
        min_confidence: Decimal | str | float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[EntitySearchResult]:
        statement = self.build_search_entities_statement(
            text_query=text_query,
            entity_types=entity_types,
            statuses=statuses,
            applies_to=applies_to,
            scope=scope,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )
        rows = self.session.execute(statement).all()
        return [
            EntitySearchResult(entity=row[0], rank_score=float(row.rank_score or 0))
            for row in rows
        ]

    def build_search_entities_statement(
        self,
        *,
        text_query: str | None = None,
        entity_types: Sequence[str] | None = None,
        statuses: Sequence[str] | None = ("active",),
        applies_to: dict[str, Any] | None = None,
        scope: str | None = None,
        min_confidence: Decimal | str | float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Select[Any]:
        name_match_score = _entity_text_score(text_query).label("rank_score")
        statement = select(Entity, name_match_score)

        if text_query:
            like_query = f"%{text_query}%"
            statement = statement.where(
                or_(
                    Entity.name.ilike(like_query),
                    Entity.entity_type.ilike(like_query),
                )
            )
        if entity_types:
            statement = statement.where(Entity.entity_type.in_(list(entity_types)))
        if statuses:
            statement = statement.where(Entity.status.in_(list(statuses)))
        if applies_to:
            statement = statement.where(Entity.applies_to.contains(applies_to))
        if scope:
            statement = statement.where(Entity.applies_to.contains({"scope": scope}))
        if min_confidence is not None:
            statement = statement.where(Entity.confidence >= _decimal_value(min_confidence))

        return statement.order_by(name_match_score.desc(), Entity.name).limit(limit).offset(offset)

    def search_hierarchical_memories(
        self,
        *,
        workspace: str | None = None,
        repo: str | None = None,
        project: str | None = None,
        component: str | None = None,
        topic: str | None = None,
        text_query: str | None = None,
        memory_types: Sequence[str] | None = None,
        statuses: Sequence[str] | None = ("active",),
        sensitivities: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        applies_to: dict[str, Any] | None = None,
        scope: str | None = None,
        min_confidence: Decimal | str | float | None = None,
        since: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
        include_global: bool = True,
        scope_path: Sequence[str] | None = None,
        include_inherited: bool = True,
        valid_at: datetime | None = None,
        cited_path: str | None = None,
    ) -> list[MemorySearchResult]:
        if scope_path:
            return self.search_scope_path_memories(
                scope_path=scope_path,
                include_inherited=include_inherited,
                valid_at=valid_at,
                text_query=text_query,
                memory_types=memory_types,
                statuses=statuses,
                sensitivities=sensitivities,
                tags=tags,
                metadata_filter=metadata_filter,
                applies_to=applies_to,
                scope=scope,
                min_confidence=min_confidence,
                since=since,
                limit=limit,
                offset=offset,
            )

        search_limit = limit + max(offset, 0)
        layers = _hierarchy_layers(
            workspace=workspace,
            repo=repo,
            project=project,
            component=component,
            topic=topic,
            include_global=include_global,
        )
        layer_caps = _allocate_layer_caps(limit=search_limit, layer_count=len(layers))
        layer_results: list[tuple[str, int, list[MemorySearchResult]]] = []

        for index, layer in enumerate(layers):
            layer_applies_to = _layer_applies_to(
                applies_to=applies_to,
                memory_scope=layer["memory_scope"],
                workspace=layer.get("workspace"),
                repo=layer.get("repo"),
                project=layer.get("project"),
                component=layer.get("component"),
                topic=layer.get("topic"),
            )
            results = self.search_memories(
                text_query=text_query,
                memory_types=memory_types,
                statuses=statuses,
                sensitivities=sensitivities,
                tags=tags,
                metadata_filter=metadata_filter,
                applies_to=layer_applies_to,
                scope=scope,
                min_confidence=min_confidence,
                since=since,
                limit=max(search_limit, layer_caps[index]),
                offset=0,
                cited_path=cited_path,
            )
            layer_results.append((layer["memory_scope"], layer_caps[index], results))

        combined = _merge_layered_memory_results(layer_results, limit=search_limit)
        return combined[offset : offset + limit]

    def search_scope_path_memories(
        self,
        *,
        scope_path: Sequence[str],
        include_inherited: bool = True,
        valid_at: datetime | None = None,
        text_query: str | None = None,
        entity_id: UUID | None = None,
        memory_types: Sequence[str] | None = None,
        statuses: Sequence[str] | None = ("active",),
        sensitivities: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        applies_to: dict[str, Any] | None = None,
        scope: str | None = None,
        min_confidence: Decimal | str | float | None = None,
        since: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
        cited_path: str | None = None,
    ) -> list[MemorySearchResult]:
        search_limit = limit + max(offset, 0)
        layers = scope_path_layers(scope_path, include_inherited=include_inherited)
        layer_caps = _allocate_layer_caps(limit=search_limit, layer_count=len(layers))
        layer_results: list[tuple[tuple[str, ...], int, list[MemorySearchResult]]] = []

        for index, layer_scope_path in enumerate(layers):
            results = self.search_memories(
                text_query=text_query,
                entity_id=entity_id,
                memory_types=memory_types,
                statuses=statuses,
                sensitivities=sensitivities,
                tags=tags,
                metadata_filter=metadata_filter,
                applies_to=without_applies_to_keys(applies_to, SCOPE_PATH_KEY),
                scope=scope,
                scope_path=layer_scope_path,
                min_confidence=min_confidence,
                since=since,
                limit=max(search_limit * 2, layer_caps[index]),
                offset=0,
                cited_path=cited_path,
            )
            valid_results = [
                result
                for result in results
                if _memory_valid_at(result.memory, valid_at or datetime.now(timezone.utc))
            ]
            layer_results.append((layer_scope_path, layer_caps[index], valid_results))

        combined = _merge_scope_path_memory_results(layer_results, limit=search_limit)
        return combined[offset : offset + limit]

    def search_project_and_global_memories(
        self,
        project: str,
        *,
        repo: str | None = None,
        **kwargs: Any,
    ) -> list[MemorySearchResult]:
        return self.search_hierarchical_memories(project=project, repo=repo, **kwargs)

    def list_liked_items_by_genre(
        self,
        genre: str,
        *,
        person_id: UUID | None = None,
        sensitivities: Sequence[str] | None = ("normal",),
        limit: int = 20,
    ) -> list[Memory]:
        return self._list_entertainment_items_by_genre(
            genre,
            liked=True,
            person_id=person_id,
            sensitivities=sensitivities,
            limit=limit,
        )

    def list_disliked_items_by_genre(
        self,
        genre: str,
        *,
        person_id: UUID | None = None,
        sensitivities: Sequence[str] | None = ("normal",),
        limit: int = 20,
    ) -> list[Memory]:
        return self._list_entertainment_items_by_genre(
            genre,
            liked=False,
            person_id=person_id,
            sensitivities=sensitivities,
            limit=limit,
        )

    def get_medications_for_person(
        self,
        person_id: UUID,
        *,
        include_archived: bool = False,
        include_sensitive: bool = False,
    ) -> list[Memory]:
        statuses = None if include_archived else ("active",)
        sensitivities = ("normal", "sensitive", "private") if include_sensitive else ("normal",)
        results = self.search_memories(
            memory_types=("medication",),
            statuses=statuses,
            sensitivities=sensitivities,
            applies_to={"person_id": str(person_id)},
            limit=100,
        )
        return [result.memory for result in results]

    def get_entertainment_profile(self, person_id: UUID) -> dict[str, list[Memory]]:
        liked = self.search_memories(
            memory_types=("entertainment_preference",),
            tags=("liked",),
            applies_to={"person_id": str(person_id)},
            limit=50,
        )
        disliked = self.search_memories(
            memory_types=("entertainment_preference",),
            tags=("disliked",),
            applies_to={"person_id": str(person_id)},
            limit=50,
        )
        inferred = self.search_memories(
            memory_types=("inferred_preference",),
            applies_to={"person_id": str(person_id), "inferred": True},
            min_confidence=Decimal("0.5"),
            limit=50,
        )
        return {
            "liked": [result.memory for result in liked],
            "disliked": [result.memory for result in disliked],
            "inferred": [result.memory for result in inferred],
        }

    def get_project_context(
        self,
        project: str,
        *,
        workspace: str | None = None,
        component: str | None = None,
        topic: str | None = None,
        limit: int = 20,
    ) -> list[Memory]:
        results = self.search_hierarchical_memories(
            workspace=workspace,
            project=project,
            component=component,
            topic=topic,
            memory_types=PROJECT_CONTEXT_MEMORY_TYPES,
            statuses=("active",),
            scope="development",
            limit=limit,
        )
        return [result.memory for result in results]

    def vector_search_plan(self, *, embedding_dimensions: int | None = None) -> VectorSearchPlan:
        return VectorSearchPlan(
            status="scaffold_only",
            reason="Embedding generation and vector query execution are intentionally not implemented yet.",
            embedding_dimensions=embedding_dimensions,
        )

    def _list_entertainment_items_by_genre(
        self,
        genre: str,
        *,
        liked: bool,
        person_id: UUID | None,
        sensitivities: Sequence[str] | None,
        limit: int,
    ) -> list[Memory]:
        statement = self.build_entertainment_items_by_genre_statement(
            genre,
            liked=liked,
            person_id=person_id,
            sensitivities=sensitivities,
            limit=limit,
        )
        rows = self.session.execute(statement).all()
        return [row[0] for row in rows]

    def build_entertainment_items_by_genre_statement(
        self,
        genre: str,
        *,
        liked: bool,
        person_id: UUID | None = None,
        sensitivities: Sequence[str] | None = ("normal",),
        limit: int = 20,
    ) -> Select[Any]:
        tag_name = "liked" if liked else "disliked"
        item_entity = aliased(Entity)
        genre_entity = aliased(Entity)
        text_rank = literal(0.0).label("text_rank")
        recency_score = _recency_score(Memory.created_at)
        rank_score = (
            (cast(Memory.confidence, Float) * literal(2.0)) + recency_score
        ).label("rank_score")

        statement = (
            select(Memory, rank_score, text_rank, recency_score.label("recency_score"))
            .join(MemoryTag, MemoryTag.memory_id == Memory.id)
            .join(item_entity, item_entity.id == Memory.entity_id)
            .join(Relationship, Relationship.source_entity_id == item_entity.id)
            .join(genre_entity, genre_entity.id == Relationship.target_entity_id)
            .where(
                Memory.memory_type == "entertainment_preference",
                Memory.status == "active",
                MemoryTag.tag == tag_name,
                MemoryTag.status == "active",
                Relationship.relationship_type == "has_genre",
                Relationship.status == "active",
                genre_entity.entity_type == "genre",
                or_(
                    genre_entity.name.ilike(f"%{genre}%"),
                    genre_entity.aliases.contains([genre]),
                ),
            )
            .order_by(rank_score.desc(), Memory.created_at.desc(), Memory.id)
            .limit(limit)
        )
        if person_id is not None:
            statement = statement.where(Memory.applies_to.contains({"person_id": str(person_id)}))
        if sensitivities:
            statement = statement.where(Memory.sensitivity.in_(list(sensitivities)))
        return statement

    def traverse_entity_graph(
        self,
        start_entity_id: str,
        relationship_types: tuple[str, ...] | None = None,
        direction: str = "both",
        max_depth: int = 2,
        include_memories: bool = True,
        limit: int = 20,
    ) -> dict[str, Any]:
        """BFS traversal of the entity graph from start_entity_id."""
        from uuid import UUID

        from memory_mcp.models import Memory
        from memory_mcp.repositories.entities import EntityRepository
        from memory_mcp.repositories.relationships import RelationshipRepository

        entity_repo = EntityRepository(self.session)
        rel_repo = RelationshipRepository(self.session)

        try:
            start_uuid = UUID(start_entity_id)
        except ValueError:
            return {"start_entity_id": start_entity_id, "node_count": 0, "edge_count": 0,
                    "nodes": [], "edges": [], "memories": []}

        visited_ids: set[str] = set()
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        queue: list[tuple[str, int]] = [(start_entity_id, 0)]

        while queue and len(nodes) < limit:
            eid, depth = queue.pop(0)
            if eid in visited_ids or depth > max_depth:
                continue
            visited_ids.add(eid)
            entity = entity_repo.get(UUID(eid))
            if entity is None:
                continue
            nodes.append({
                "id": str(entity.id),
                "entity_type": entity.entity_type,
                "name": entity.name,
                "aliases": entity.aliases or [],
                "attributes": entity.attributes or {},
            })
            if depth < max_depth:
                rels = rel_repo.neighbors(UUID(eid), relationship_types, direction)
                for rel in rels:
                    src_str = str(rel.source_entity_id)
                    tgt_str = str(rel.target_entity_id)
                    neighbor_id = tgt_str if src_str == eid else src_str
                    edges.append({
                        "source": src_str,
                        "target": tgt_str,
                        "type": rel.relationship_type,
                        "description": rel.description,
                    })
                    if neighbor_id not in visited_ids:
                        queue.append((neighbor_id, depth + 1))

        memories: list[dict[str, Any]] = []
        if include_memories:
            from sqlalchemy import select as sa_select
            for node in nodes[:10]:
                ms = list(self.session.scalars(
                    sa_select(Memory)
                    .where(Memory.entity_id == UUID(node["id"]))
                    .where(Memory.status == "active")
                    .limit(3)
                ))
                for m in ms:
                    memories.append({
                        "entity_id": node["id"],
                        "memory_id": str(m.id),
                        "content": m.content,
                    })

        return {
            "start_entity_id": start_entity_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
            "memories": memories,
        }


def _memory_search_vector() -> Any:
    return func.to_tsvector(
        literal_column("'english'"),
        func.coalesce(Memory.content, literal_column("''"))
        + literal_column("' '")
        + func.coalesce(Memory.summary, literal_column("''")),
    )


def _plain_text_query(text_query: str) -> Any:
    tokens = re.findall(r"[A-Za-z0-9]+", text_query)
    if not tokens:
        return func.plainto_tsquery(literal_column("'english'"), text_query)
    return func.to_tsquery(literal_column("'english'"), " | ".join(tokens))


def _memory_text_rank(text_query: str | None) -> Any:
    if not text_query:
        return literal(0.0)
    return func.ts_rank_cd(_memory_search_vector(), _plain_text_query(text_query))


def _recency_score(created_at: Any) -> Any:
    age_days = func.extract("epoch", func.now() - created_at) / literal(86400.0)
    return literal(1.0) / (literal(1.0) + (age_days / literal(30.0)))


def _entity_text_score(text_query: str | None) -> Any:
    if not text_query:
        return cast(Entity.confidence, Float) * literal(2.0)
    exact_name = func.lower(Entity.name) == text_query.lower()
    prefix_name = func.lower(Entity.name).like(f"{text_query.lower()}%")
    return (
        case((exact_name, literal(3.0)), (prefix_name, literal(2.0)), else_=literal(1.0))
        + (cast(Entity.confidence, Float) * literal(2.0))
    )


def _dedupe_memories(results: Sequence[MemorySearchResult]) -> list[Memory]:
    seen: set[UUID] = set()
    memories: list[Memory] = []
    for result in sorted(results, key=lambda item: item.rank_score, reverse=True):
        memory_id = result.memory.id
        if memory_id in seen:
            continue
        seen.add(memory_id)
        memories.append(result.memory)
    return memories


def _merge_scoped_memory_results(
    project_results: Sequence[MemorySearchResult],
    global_results: Sequence[MemorySearchResult],
) -> list[MemorySearchResult]:
    return _merge_layered_memory_results(
        [
            (PROJECT_MEMORY_SCOPE, len(project_results), list(project_results)),
            (GLOBAL_MEMORY_SCOPE, len(global_results), list(global_results)),
        ],
        limit=len(project_results) + len(global_results),
    )


def _hierarchy_layers(
    *,
    workspace: str | None,
    repo: str | None,
    project: str | None,
    component: str | None,
    topic: str | None,
    include_global: bool,
) -> list[dict[str, str]]:
    layers: list[dict[str, str]] = []
    if component:
        layer = {
            "memory_scope": COMPONENT_MEMORY_SCOPE,
            "component": component,
        }
        if project:
            layer["project"] = project
        if repo:
            layer["repo"] = repo
        if workspace:
            layer["workspace"] = workspace
        if topic:
            layer["topic"] = topic
        layers.append(layer)
    elif project:
        layer = {
            "memory_scope": COMPONENT_MEMORY_SCOPE,
            "project": project,
        }
        if repo:
            layer["repo"] = repo
        if workspace:
            layer["workspace"] = workspace
        layers.append(layer)
    if project:
        layer = {
            "memory_scope": PROJECT_MEMORY_SCOPE,
            "project": project,
        }
        if repo:
            layer["repo"] = repo
        if workspace:
            layer["workspace"] = workspace
        layers.append(layer)
    if workspace:
        layers.append(
            {
                "memory_scope": WORKSPACE_MEMORY_SCOPE,
                "workspace": workspace,
            }
        )
    if include_global or not layers:
        layers.append({"memory_scope": GLOBAL_MEMORY_SCOPE})
    return layers


def _layer_applies_to(
    *,
    applies_to: dict[str, Any] | None,
    memory_scope: str,
    workspace: str | None = None,
    repo: str | None = None,
    project: str | None = None,
    component: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    if memory_scope == GLOBAL_MEMORY_SCOPE:
        base = without_applies_to_keys(
            applies_to,
            WORKSPACE_KEY,
            REPO_KEY,
            PROJECT_KEY,
            COMPONENT_KEY,
            TOPIC_KEY,
        )
        return with_memory_scope(base, memory_scope=GLOBAL_MEMORY_SCOPE)
    return with_memory_scope(
        applies_to,
        memory_scope=memory_scope,
        workspace=workspace,
        repo=repo,
        project=project,
        component=component,
        topic=topic,
    )


def _allocate_layer_caps(*, limit: int, layer_count: int) -> list[int]:
    if layer_count <= 0:
        return []
    weights = list(range(layer_count, 0, -1))
    total_weight = sum(weights)
    caps = [max(1, (limit * weight) // total_weight) for weight in weights]
    allocated = sum(caps)
    while allocated > limit:
        for index in range(layer_count - 1, -1, -1):
            if caps[index] > 1 and allocated > limit:
                caps[index] -= 1
                allocated -= 1
    while allocated < limit:
        for index in range(layer_count):
            if allocated >= limit:
                break
            caps[index] += 1
            allocated += 1
    return caps


def _merge_layered_memory_results(
    layered_results: Sequence[tuple[str, int, Sequence[MemorySearchResult]]],
    *,
    limit: int,
) -> list[MemorySearchResult]:
    seen: set[UUID] = set()
    merged: list[MemorySearchResult] = []
    leftovers: list[tuple[str, Sequence[MemorySearchResult]]] = []

    for _layer_name, cap, results in layered_results:
        taken = 0
        remaining: list[MemorySearchResult] = []
        for result in results:
            memory_id = result.memory.id
            if memory_id in seen:
                continue
            if taken < cap and len(merged) < limit:
                seen.add(memory_id)
                merged.append(result)
                taken += 1
            else:
                remaining.append(result)
        leftovers.append((_layer_name, remaining))

    if len(merged) >= limit:
        return merged[:limit]

    for _layer_name, results in leftovers:
        for result in results:
            memory_id = result.memory.id
            if memory_id in seen:
                continue
            seen.add(memory_id)
            merged.append(result)
            if len(merged) >= limit:
                return merged
    return merged


def _merge_scope_path_memory_results(
    layered_results: Sequence[tuple[tuple[str, ...], int, Sequence[MemorySearchResult]]],
    *,
    limit: int,
) -> list[MemorySearchResult]:
    seen: set[UUID] = set()
    overridden_by_lower_scope: set[str] = set()
    merged: list[MemorySearchResult] = []
    leftovers: list[Sequence[MemorySearchResult]] = []

    for _scope_path, cap, results in layered_results:
        inherited_overrides = set(overridden_by_lower_scope)
        layer_overrides = _overridden_memory_ids(results)
        taken = 0
        remaining: list[MemorySearchResult] = []

        for result in results:
            memory_id = result.memory.id
            if memory_id in seen or str(memory_id) in inherited_overrides:
                continue
            if taken < cap and len(merged) < limit:
                seen.add(memory_id)
                merged.append(result)
                taken += 1
            else:
                remaining.append(result)

        overridden_by_lower_scope.update(layer_overrides)
        leftovers.append(remaining)

    if len(merged) >= limit:
        return merged[:limit]

    for results in leftovers:
        for result in results:
            memory_id = result.memory.id
            if memory_id in seen or str(memory_id) in overridden_by_lower_scope:
                continue
            seen.add(memory_id)
            merged.append(result)
            if len(merged) >= limit:
                return merged
    return merged


def _overridden_memory_ids(results: Sequence[MemorySearchResult]) -> set[str]:
    overridden: set[str] = set()
    for result in results:
        metadata = result.memory.metadata_ or {}
        applies_to = result.memory.applies_to or {}
        for source in (metadata, applies_to):
            value = source.get(OVERRIDES_MEMORY_IDS_KEY)
            if isinstance(value, str):
                overridden.add(value)
            elif isinstance(value, Sequence):
                overridden.update(str(item) for item in value if item)
    return overridden


def _memory_valid_at(memory: Memory, valid_at: datetime) -> bool:
    applies_to = memory.applies_to or {}
    valid_from = _parse_scope_datetime(applies_to.get(VALID_FROM_KEY))
    valid_to = _parse_scope_datetime(applies_to.get(VALID_TO_KEY))
    if valid_from is not None and valid_at < valid_from:
        return False
    if valid_to is not None and valid_at >= valid_to:
        return False
    return True


def _parse_scope_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _decimal_value(value: Decimal | str | float) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
