"""MCP server exposing personal memory tools."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, select

from memory_mcp.db import session_scope
from memory_mcp.models import Entity, Memory, MemoryTag, Relationship
from memory_mcp.pruning import PruningService
from memory_mcp.retrieval import HybridRetrievalService, MemorySearchResult
from memory_mcp.scopes import (
    COMPONENT_MEMORY_SCOPE,
    GLOBAL_MEMORY_SCOPE,
    OVERRIDES_MEMORY_IDS_KEY,
    PROJECT_MEMORY_SCOPE,
    SCOPE_PATH_KEY,
    WORKSPACE_MEMORY_SCOPE,
    with_default_scope,
    with_memory_scope,
    with_scope_path,
)
from memory_mcp.services import ContextPacket, ContextSynthesisService, MemoryService

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_runtime_env() -> None:
    env_file = Path(os.getenv("MEMORY_MCP_ENV_FILE", PROJECT_ROOT / ".env"))
    load_dotenv(dotenv_path=env_file, override=False)


_load_runtime_env()

mcp = FastMCP("memory-mcp")

DEFAULT_SENSITIVITIES = ("normal",)
ALL_SENSITIVITIES = ("normal", "sensitive", "private")
VALID_SENSITIVITIES = set(ALL_SENSITIVITIES)
VALID_MEMORY_SCOPES = {
    COMPONENT_MEMORY_SCOPE,
    GLOBAL_MEMORY_SCOPE,
    PROJECT_MEMORY_SCOPE,
    WORKSPACE_MEMORY_SCOPE,
}
MAX_TEXT_CHARS = 20_000
MAX_SUMMARY_CHARS = 2_000
MAX_JSON_CHARS = 20_000
MAX_TAGS = 25
MAX_TAG_CHARS = 100
MAX_SEARCH_LIMIT = 50
MAX_CONTEXT_MEMORIES = 20
DEFAULT_CONTEXT_TOKENS = 1200
MAX_CONTEXT_TOKENS = 6000
MAX_SCOPE_PATH_PARTS = 32
MAX_SCOPE_PATH_PART_CHARS = 200
MUTATION_TOOLS_ENV = "MEMORY_MCP_ENABLE_MUTATION_TOOLS"
SENSITIVE_TOOLS_ENV = "MEMORY_MCP_ENABLE_SENSITIVE_TOOLS"
CACHE_NAMESPACE = "memory-data"
CACHE_SOURCE_TABLES = (
    ("entities", Entity),
    ("memories", Memory),
    ("memory_tags", MemoryTag),
    ("relationships", Relationship),
)


@mcp.tool()
def add_memory(
    memory_type: str,
    content: str,
    entity_id: str | None = None,
    summary: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    confidence: float = 1.0,
    sensitivity: str = "normal",
    applies_to: dict[str, Any] | None = None,
    memory_scope: str | None = None,
    workspace: str | None = None,
    project: str | None = None,
    component: str | None = None,
    topic: str | None = None,
    scope_path: list[str] | None = None,
    scope_type: str | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
    overrides_memory_ids: list[str] | None = None,
    tags: list[str] | None = None,
    include_content: bool = False,
    include_evidence: bool = False,
) -> dict[str, Any]:
    """Add a memory and optional tags."""

    _require_mutation_tools_enabled()
    content = _validate_text("content", content, max_chars=MAX_TEXT_CHARS, required=True)
    summary = _validate_text("summary", summary, max_chars=MAX_SUMMARY_CHARS)
    evidence = _validate_json_payload("evidence", evidence, max_chars=MAX_JSON_CHARS)
    metadata = _validate_json_payload("metadata", metadata, max_chars=MAX_JSON_CHARS)
    applies_to = _validate_json_payload("applies_to", applies_to, max_chars=MAX_JSON_CHARS)
    memory_scope = _validate_memory_scope(memory_scope)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    project = _validate_text("project", project, max_chars=200)
    component = _validate_text("component", component, max_chars=200)
    topic = _validate_text("topic", topic, max_chars=200)
    scope_path = _validate_scope_path(scope_path)
    scope_type = _validate_text("scope_type", scope_type, max_chars=64)
    valid_from = _validate_text("valid_from", valid_from, max_chars=64)
    valid_to = _validate_text("valid_to", valid_to, max_chars=64)
    overrides_memory_ids = _validate_uuid_list("overrides_memory_ids", overrides_memory_ids)
    tags = _validate_tags(tags)
    confidence = _validate_confidence(confidence)
    sensitivity = _validate_sensitivity(sensitivity)
    if component and memory_scope is None:
        memory_scope = COMPONENT_MEMORY_SCOPE
    elif project and memory_scope is None:
        memory_scope = PROJECT_MEMORY_SCOPE
    elif workspace and memory_scope is None:
        memory_scope = WORKSPACE_MEMORY_SCOPE
    _validate_scope_requirements(
        memory_scope=memory_scope,
        workspace=workspace,
        project=project,
        component=component,
    )
    if memory_scope is not None:
        applies_to = _scoped_applies_to(
            applies_to=applies_to,
            memory_scope=memory_scope,
            workspace=workspace,
            project=project,
            component=component,
            topic=topic,
        )
    if scope_path is not None:
        applies_to = with_scope_path(
            applies_to,
            scope_path=scope_path,
            scope_type=scope_type,
            valid_from=valid_from,
            valid_to=valid_to,
        )
    if overrides_memory_ids:
        metadata = {
            **(metadata or {}),
            OVERRIDES_MEMORY_IDS_KEY: overrides_memory_ids,
        }

    with session_scope() as session:
        service = MemoryService(session)
        memory = service.create_memory(
            memory_type=memory_type,
            content=content,
            entity_id=_parse_uuid(entity_id),
            summary=summary,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            applies_to=applies_to,
        )
        created_tags = [service.tag_memory(memory.id, tag) for tag in tags or []]
        _require_sensitive_echo_allowed(
            memory.sensitivity,
            include_content=include_content,
            include_evidence=include_evidence,
        )
        return {
            "memory": _memory_write_to_dict(
                memory,
                include_content=include_content,
                include_evidence=include_evidence,
            ),
            "tags": _tags_to_dict(created_tags),
            "cache": _cache_metadata(_cache_state_from_session(session), hit=False),
        }


@mcp.tool()
def archive_memory(
    memory_id: str,
    include_evidence: bool = False,
) -> dict[str, Any]:
    """Archive an existing memory by UUID."""

    _require_mutation_tools_enabled()
    with session_scope() as session:
        service = MemoryService(session)
        memory = service.archive_memory(_parse_required_uuid(memory_id, "memory_id"))
        return {
            "memory": _memory_to_dict(memory, include_evidence=include_evidence),
            "cache": _cache_metadata(_cache_state_from_session(session), hit=False),
        }


@mcp.tool()
def supersede_memory(
    memory_id: str,
    memory_type: str,
    content: str,
    entity_id: str | None = None,
    summary: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    confidence: float = 1.0,
    sensitivity: str | None = None,
    applies_to: dict[str, Any] | None = None,
    memory_scope: str | None = None,
    workspace: str | None = None,
    project: str | None = None,
    component: str | None = None,
    topic: str | None = None,
    scope_path: list[str] | None = None,
    scope_type: str | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
    overrides_memory_ids: list[str] | None = None,
    tags: list[str] | None = None,
    include_content: bool = False,
    include_evidence: bool = False,
) -> dict[str, Any]:
    """Supersede an existing memory with a replacement memory."""

    _require_mutation_tools_enabled()
    content = _validate_text("content", content, max_chars=MAX_TEXT_CHARS, required=True)
    summary = _validate_text("summary", summary, max_chars=MAX_SUMMARY_CHARS)
    evidence = _validate_json_payload("evidence", evidence, max_chars=MAX_JSON_CHARS)
    metadata = _validate_json_payload("metadata", metadata, max_chars=MAX_JSON_CHARS)
    applies_to = _validate_json_payload("applies_to", applies_to, max_chars=MAX_JSON_CHARS)
    memory_scope = _validate_memory_scope(memory_scope)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    project = _validate_text("project", project, max_chars=200)
    component = _validate_text("component", component, max_chars=200)
    topic = _validate_text("topic", topic, max_chars=200)
    scope_path = _validate_scope_path(scope_path)
    scope_type = _validate_text("scope_type", scope_type, max_chars=64)
    valid_from = _validate_text("valid_from", valid_from, max_chars=64)
    valid_to = _validate_text("valid_to", valid_to, max_chars=64)
    overrides_memory_ids = _validate_uuid_list("overrides_memory_ids", overrides_memory_ids)
    tags = _validate_tags(tags)
    confidence = _validate_confidence(confidence)
    sensitivity = None if sensitivity is None else _validate_sensitivity(sensitivity)
    if component and memory_scope is None:
        memory_scope = COMPONENT_MEMORY_SCOPE
    elif project and memory_scope is None:
        memory_scope = PROJECT_MEMORY_SCOPE
    elif workspace and memory_scope is None:
        memory_scope = WORKSPACE_MEMORY_SCOPE
    _validate_scope_requirements(
        memory_scope=memory_scope,
        workspace=workspace,
        project=project,
        component=component,
    )
    if memory_scope is not None:
        applies_to = _scoped_applies_to(
            applies_to=applies_to,
            memory_scope=memory_scope,
            workspace=workspace,
            project=project,
            component=component,
            topic=topic,
        )
    if scope_path is not None:
        applies_to = with_scope_path(
            applies_to,
            scope_path=scope_path,
            scope_type=scope_type,
            valid_from=valid_from,
            valid_to=valid_to,
        )
    if overrides_memory_ids:
        metadata = {
            **(metadata or {}),
            OVERRIDES_MEMORY_IDS_KEY: overrides_memory_ids,
        }

    with session_scope() as session:
        service = MemoryService(session)
        memory = service.supersede_memory(
            _parse_required_uuid(memory_id, "memory_id"),
            memory_type=memory_type,
            content=content,
            entity_id=_parse_uuid(entity_id),
            summary=summary,
            evidence=evidence,
            metadata=metadata,
            confidence=confidence,
            sensitivity=sensitivity,
            applies_to=applies_to,
        )
        created_tags = [service.tag_memory(memory.id, tag) for tag in tags or []]
        _require_sensitive_echo_allowed(
            memory.sensitivity,
            include_content=include_content,
            include_evidence=include_evidence,
        )
        return {
            "superseded_memory_id": memory_id,
            "memory": _memory_write_to_dict(
                memory,
                include_content=include_content,
                include_evidence=include_evidence,
            ),
            "tags": _tags_to_dict(created_tags),
            "cache": _cache_metadata(_cache_state_from_session(session), hit=False),
        }


@mcp.tool()
def get_memory_cache_state() -> dict[str, Any]:
    """Return a cheap version token clients can use to validate cached memory reads."""

    with session_scope() as session:
        return {
            "cache": _cache_metadata(_cache_state_from_session(session), hit=False),
        }


@mcp.tool()
def search_memory(
    query: str | None = None,
    memory_types: list[str] | None = None,
    tags: list[str] | None = None,
    scope: str | None = None,
    applies_to: dict[str, Any] | None = None,
    workspace: str | None = None,
    project: str | None = None,
    component: str | None = None,
    topic: str | None = None,
    scope_path: list[str] | None = None,
    include_inherited: bool = True,
    min_confidence: float | None = 0.5,
    limit: int = 10,
    include_evidence: bool = False,
    include_sensitive: bool = False,
    include_global: bool = True,
    if_cache_version: str | None = None,
) -> dict[str, Any]:
    """Search memories with structured filters, tags, full text, confidence, and scope."""

    query = _validate_text("query", query, max_chars=2_000)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    project = _validate_text("project", project, max_chars=200)
    component = _validate_text("component", component, max_chars=200)
    topic = _validate_text("topic", topic, max_chars=200)
    scope_path = _validate_scope_path(scope_path)
    tags = _validate_tags(tags)
    memory_types = _validate_string_list("memory_types", memory_types, max_items=25, max_chars=64)
    applies_to = _validate_json_payload("applies_to", applies_to, max_chars=MAX_JSON_CHARS)
    limit = _bounded_int("limit", limit, minimum=1, maximum=MAX_SEARCH_LIMIT)
    min_confidence = None if min_confidence is None else _validate_confidence(min_confidence)
    sensitivities = _allowed_sensitivities(include_sensitive)
    if_cache_version = _validate_cache_version(if_cache_version)

    with session_scope() as session:
        cache_state = _cache_state_from_session(session)
        if _cache_is_fresh(cache_state, if_cache_version):
            return _cached_response(cache_state)
        retrieval = HybridRetrievalService(session)
        if scope_path:
            results = retrieval.search_scope_path_memories(
                scope_path=scope_path,
                include_inherited=include_inherited,
                text_query=query,
                memory_types=_tuple_or_none(memory_types),
                tags=_tuple_or_none(tags),
                scope=scope,
                applies_to=applies_to,
                min_confidence=min_confidence,
                sensitivities=sensitivities,
                limit=limit,
            )
        elif workspace or project or component:
            results = retrieval.search_hierarchical_memories(
                workspace=workspace,
                project=project,
                component=component,
                topic=topic,
                text_query=query,
                memory_types=_tuple_or_none(memory_types),
                tags=_tuple_or_none(tags),
                scope=scope,
                applies_to=applies_to,
                min_confidence=min_confidence,
                sensitivities=sensitivities,
                limit=limit,
                include_global=include_global,
            )
        else:
            results = retrieval.search_memories(
                text_query=query,
                memory_types=_tuple_or_none(memory_types),
                tags=_tuple_or_none(tags),
                scope=scope,
                applies_to=applies_to,
                min_confidence=min_confidence,
                sensitivities=sensitivities,
                limit=limit,
            )
        return {
            "query": query,
            "workspace": workspace,
            "project": project,
            "component": component,
            "topic": topic,
            "scope_path": scope_path,
            "include_inherited": include_inherited,
            "count": len(results),
            "results": [_memory_result_to_dict(result, include_evidence=include_evidence) for result in results],
            "cache": _cache_metadata(cache_state, hit=False),
        }


@mcp.tool()
def get_context_packet(
    request: str,
    include_evidence: bool = False,
    max_memories: int = 8,
    max_tokens: int = DEFAULT_CONTEXT_TOKENS,
    include_sensitive: bool = False,
    workspace: str | None = None,
    project: str | None = None,
    component: str | None = None,
    topic: str | None = None,
    scope_path: list[str] | None = None,
    include_inherited: bool = True,
    include_global: bool = True,
    if_cache_version: str | None = None,
) -> dict[str, Any]:
    """Generate a compact LLM-ready context packet for a request."""

    request = _validate_text("request", request, max_chars=2_000, required=True)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    project = _validate_text("project", project, max_chars=200)
    component = _validate_text("component", component, max_chars=200)
    topic = _validate_text("topic", topic, max_chars=200)
    scope_path = _validate_scope_path(scope_path)
    max_memories = _bounded_int(
        "max_memories",
        max_memories,
        minimum=1,
        maximum=MAX_CONTEXT_MEMORIES,
    )
    max_tokens = _bounded_int(
        "max_tokens",
        max_tokens,
        minimum=100,
        maximum=MAX_CONTEXT_TOKENS,
    )
    if_cache_version = _validate_cache_version(if_cache_version)
    with session_scope() as session:
        cache_state = _cache_state_from_session(session)
        if _cache_is_fresh(cache_state, if_cache_version):
            return _cached_response(cache_state)
        packet = ContextSynthesisService(session).synthesize_context(
            request,
            include_evidence=include_evidence,
            max_memories=max_memories,
            sensitivities=_allowed_sensitivities(include_sensitive),
            workspace=workspace,
            project=project,
            component=component,
            topic=topic,
            scope_path=scope_path,
            include_inherited=include_inherited,
            include_global=include_global,
            max_tokens=max_tokens,
        )
        data = _context_packet_to_dict(packet)
        data["cache"] = _cache_metadata(cache_state, hit=False)
        return data


@mcp.tool()
def list_preferences(
    domain: str | None = None,
    person_id: str | None = None,
    workspace: str | None = None,
    project: str | None = None,
    component: str | None = None,
    scope_path: list[str] | None = None,
    include_inherited: bool = True,
    limit: int = 20,
    include_sensitive: bool = False,
    include_global: bool = True,
    if_cache_version: str | None = None,
) -> dict[str, Any]:
    """List active preference memories, optionally scoped by domain or person."""

    workspace = _validate_text("workspace", workspace, max_chars=200)
    project = _validate_text("project", project, max_chars=200)
    component = _validate_text("component", component, max_chars=200)
    scope_path = _validate_scope_path(scope_path)
    limit = _bounded_int("limit", limit, minimum=1, maximum=MAX_SEARCH_LIMIT)
    memory_types = _preference_memory_types(domain)
    applies_to = {"person_id": person_id} if person_id else None
    scope = _domain_scope(domain)
    if_cache_version = _validate_cache_version(if_cache_version)

    with session_scope() as session:
        cache_state = _cache_state_from_session(session)
        if _cache_is_fresh(cache_state, if_cache_version):
            return _cached_response(cache_state)
        retrieval = HybridRetrievalService(session)
        if scope_path:
            results = retrieval.search_scope_path_memories(
                scope_path=scope_path,
                include_inherited=include_inherited,
                memory_types=memory_types,
                applies_to=applies_to,
                scope=scope,
                sensitivities=_allowed_sensitivities(include_sensitive),
                limit=limit,
            )
        elif workspace or project or component:
            results = retrieval.search_hierarchical_memories(
                workspace=workspace,
                project=project,
                component=component,
                memory_types=memory_types,
                applies_to=applies_to,
                scope=scope,
                sensitivities=_allowed_sensitivities(include_sensitive),
                limit=limit,
                include_global=include_global,
            )
        else:
            results = retrieval.search_memories(
                memory_types=memory_types,
                applies_to=applies_to,
                scope=scope,
                sensitivities=_allowed_sensitivities(include_sensitive),
                limit=limit,
            )
        return {
            "domain": domain,
            "workspace": workspace,
            "project": project,
            "component": component,
            "scope_path": scope_path,
            "include_inherited": include_inherited,
            "count": len(results),
            "preferences": [_memory_result_to_dict(result) for result in results],
            "cache": _cache_metadata(cache_state, hit=False),
        }


@mcp.tool()
def list_liked_media(
    genre: str | None = None,
    person_id: str | None = None,
    limit: int = 20,
    include_sensitive: bool = False,
    if_cache_version: str | None = None,
) -> dict[str, Any]:
    """List liked media memories, optionally filtered by genre and person."""

    genre = _validate_text("genre", genre, max_chars=200)
    limit = _bounded_int("limit", limit, minimum=1, maximum=MAX_SEARCH_LIMIT)
    sensitivities = _allowed_sensitivities(include_sensitive)
    if_cache_version = _validate_cache_version(if_cache_version)
    with session_scope() as session:
        cache_state = _cache_state_from_session(session)
        if _cache_is_fresh(cache_state, if_cache_version):
            return _cached_response(cache_state)
        retrieval = HybridRetrievalService(session)
        if genre:
            memories = retrieval.list_liked_items_by_genre(
                genre,
                person_id=_parse_uuid(person_id),
                sensitivities=sensitivities,
                limit=limit,
            )
        else:
            results = retrieval.search_memories(
                memory_types=("entertainment_preference",),
                tags=("liked",),
                applies_to={"person_id": person_id} if person_id else None,
                sensitivities=sensitivities,
                limit=limit,
            )
            memories = [result.memory for result in results]
        return {
            "genre": genre,
            "count": len(memories),
            "items": [_memory_to_dict(memory) for memory in memories],
            "cache": _cache_metadata(cache_state, hit=False),
        }


@mcp.tool()
def list_disliked_media(
    genre: str | None = None,
    person_id: str | None = None,
    limit: int = 20,
    include_sensitive: bool = False,
    if_cache_version: str | None = None,
) -> dict[str, Any]:
    """List disliked media memories, optionally filtered by genre and person."""

    genre = _validate_text("genre", genre, max_chars=200)
    limit = _bounded_int("limit", limit, minimum=1, maximum=MAX_SEARCH_LIMIT)
    sensitivities = _allowed_sensitivities(include_sensitive)
    if_cache_version = _validate_cache_version(if_cache_version)
    with session_scope() as session:
        cache_state = _cache_state_from_session(session)
        if _cache_is_fresh(cache_state, if_cache_version):
            return _cached_response(cache_state)
        retrieval = HybridRetrievalService(session)
        if genre:
            memories = retrieval.list_disliked_items_by_genre(
                genre,
                person_id=_parse_uuid(person_id),
                sensitivities=sensitivities,
                limit=limit,
            )
        else:
            results = retrieval.search_memories(
                memory_types=("entertainment_preference",),
                tags=("disliked",),
                applies_to={"person_id": person_id} if person_id else None,
                sensitivities=sensitivities,
                limit=limit,
            )
            memories = [result.memory for result in results]
        return {
            "genre": genre,
            "count": len(memories),
            "items": [_memory_to_dict(memory) for memory in memories],
            "cache": _cache_metadata(cache_state, hit=False),
        }


@mcp.tool()
def list_medications_for_person(
    person_id: str,
    include_archived: bool = False,
    include_sensitive: bool = False,
    include_evidence: bool = False,
    if_cache_version: str | None = None,
) -> dict[str, Any]:
    """List medication memories for a person UUID."""

    if_cache_version = _validate_cache_version(if_cache_version)
    with session_scope() as session:
        cache_state = _cache_state_from_session(session)
        if _cache_is_fresh(cache_state, if_cache_version):
            return _cached_response(cache_state)
        retrieval = HybridRetrievalService(session)
        memories = retrieval.get_medications_for_person(
            _parse_required_uuid(person_id, "person_id"),
            include_archived=include_archived,
            include_sensitive=include_sensitive,
        )
        return {
            "person_id": person_id,
            "sensitive_data_included": include_sensitive,
            "count": len(memories),
            "medications": [_memory_to_dict(memory, include_evidence=include_evidence) for memory in memories],
            "note": None
            if include_sensitive
            else "Medication memories marked sensitive/private are omitted unless include_sensitive is true.",
            "cache": _cache_metadata(cache_state, hit=False),
        }


@mcp.tool()
def summarize_domain_profile(
    domain: str,
    person_id: str | None = None,
    workspace: str | None = None,
    project: str | None = None,
    component: str | None = None,
    topic: str | None = None,
    scope_path: list[str] | None = None,
    include_inherited: bool = True,
    max_tokens: int = DEFAULT_CONTEXT_TOKENS,
    include_evidence: bool = False,
    include_sensitive: bool = False,
    include_global: bool = True,
    if_cache_version: str | None = None,
) -> dict[str, Any]:
    """Summarize a domain profile as a compact context packet."""

    workspace = _validate_text("workspace", workspace, max_chars=200)
    project = _validate_text("project", project, max_chars=200)
    component = _validate_text("component", component, max_chars=200)
    topic = _validate_text("topic", topic, max_chars=200)
    scope_path = _validate_scope_path(scope_path)
    max_tokens = _bounded_int(
        "max_tokens",
        max_tokens,
        minimum=100,
        maximum=MAX_CONTEXT_TOKENS,
    )
    if_cache_version = _validate_cache_version(if_cache_version)
    request = _domain_profile_request(
        domain,
        person_id=person_id,
        workspace=workspace,
        project=project,
        component=component,
        topic=topic,
    )
    applies_to = {"person_id": person_id} if person_id else None
    with session_scope() as session:
        cache_state = _cache_state_from_session(session)
        if _cache_is_fresh(cache_state, if_cache_version):
            return _cached_response(cache_state)
        packet = ContextSynthesisService(session).synthesize_context(
            request,
            include_evidence=include_evidence,
            max_memories=10,
            applies_to=applies_to,
            sensitivities=_allowed_sensitivities(include_sensitive),
            workspace=workspace,
            project=project,
            component=component,
            topic=topic,
            scope_path=scope_path,
            include_inherited=include_inherited,
            include_global=include_global,
            max_tokens=max_tokens,
        )
        data = _context_packet_to_dict(packet)
        data["cache"] = _cache_metadata(cache_state, hit=False)
        return data


@mcp.tool()
def run_pruning_pass(
    stale_after_days: int = 180,
    inference_half_life_days: int = 90,
) -> dict[str, Any]:
    """Run a pruning pass that archives/supersedes/compresses without deleting evidence."""

    _require_mutation_tools_enabled()
    stale_after_days = _bounded_int(
        "stale_after_days",
        stale_after_days,
        minimum=1,
        maximum=3650,
    )
    inference_half_life_days = _bounded_int(
        "inference_half_life_days",
        inference_half_life_days,
        minimum=1,
        maximum=3650,
    )
    with session_scope() as session:
        result = PruningService(session).run_pruning(
            stale_after_days=stale_after_days,
            inference_half_life_days=inference_half_life_days,
        )
        return {
            "merged_duplicates": result.merged_duplicates,
            "archived_stale": result.archived_stale,
            "decayed_inferences": result.decayed_inferences,
            "promoted_summaries": result.promoted_summaries,
            "total_actions": result.total_actions,
            "cache": _cache_metadata(_cache_state_from_session(session), hit=False),
        }


def run() -> None:
    """Run the MCP server using the default stdio transport."""

    mcp.run()


def _cache_state_from_session(session: Any) -> dict[str, Any]:
    sources = []
    version_parts = []
    for table_name, model in CACHE_SOURCE_TABLES:
        count_value, updated_at = session.execute(
            select(func.count(model.id), func.max(model.updated_at))
        ).one()
        count = int(count_value or 0)
        updated_at_text = _format_datetime(updated_at)
        sources.append(
            {
                "table": table_name,
                "count": count,
                "max_updated_at": updated_at_text,
            }
        )
        version_parts.append(f"{table_name}:{count}:{updated_at_text or ''}")
    return {
        "namespace": CACHE_NAMESPACE,
        "version": "|".join(version_parts),
        "source_tables": sources,
    }


def _cache_metadata(cache_state: dict[str, Any], *, hit: bool) -> dict[str, Any]:
    return {
        "namespace": cache_state["namespace"],
        "version": cache_state["version"],
        "hit": hit,
        "source_tables": cache_state["source_tables"],
    }


def _cache_is_fresh(cache_state: dict[str, Any], if_cache_version: str | None) -> bool:
    return if_cache_version is not None and if_cache_version == cache_state["version"]


def _cached_response(cache_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "cached": True,
        "cache": _cache_metadata(cache_state, hit=True),
    }


def _memory_result_to_dict(result: MemorySearchResult, *, include_evidence: bool = False) -> dict[str, Any]:
    return {
        "memory": _memory_to_dict(result.memory, include_evidence=include_evidence),
        "rank_score": result.rank_score,
        "text_rank": result.text_rank,
        "recency_score": result.recency_score,
    }


def _memory_to_dict(memory: Memory, *, include_evidence: bool = False) -> dict[str, Any]:
    data = {
        "id": str(memory.id),
        "entity_id": str(memory.entity_id) if memory.entity_id else None,
        "memory_type": memory.memory_type,
        "summary": memory.summary,
        "content": memory.content,
        "confidence": float(memory.confidence) if memory.confidence is not None else None,
        "sensitivity": memory.sensitivity,
        "status": memory.status,
        "applies_to": memory.applies_to or {},
        "metadata": memory.metadata_ or {},
        "created_at": _format_datetime(memory.created_at),
        "updated_at": _format_datetime(memory.updated_at),
        "supersedes_memory_id": str(memory.supersedes_memory_id) if memory.supersedes_memory_id else None,
    }
    if include_evidence:
        data["evidence"] = memory.evidence or []
    return data


def _memory_write_to_dict(
    memory: Memory,
    *,
    include_content: bool = False,
    include_evidence: bool = False,
) -> dict[str, Any]:
    data = {
        "id": str(memory.id),
        "entity_id": str(memory.entity_id) if memory.entity_id else None,
        "memory_type": memory.memory_type,
        "sensitivity": memory.sensitivity,
        "status": memory.status,
        "supersedes_memory_id": str(memory.supersedes_memory_id) if memory.supersedes_memory_id else None,
    }
    if include_content:
        data["summary"] = memory.summary
        data["content"] = memory.content
    if include_evidence:
        data["evidence"] = memory.evidence or []
    return data


def _context_packet_to_dict(packet: ContextPacket) -> dict[str, Any]:
    return {
        "rendered": packet.render(),
        "context_quality": packet.diagnostics.get("context_quality"),
        "warnings": packet.diagnostics.get("warnings", []),
        "suggested_next_action": packet.diagnostics.get("suggested_next_action"),
        "source_read_policy": packet.diagnostics.get("source_read_policy"),
        "source_read_budget_tokens": packet.diagnostics.get("source_read_budget_tokens"),
        "source_read_limits": packet.diagnostics.get("source_read_limits"),
        "diagnostics": packet.diagnostics,
        "classification": {
            "domain": packet.classification.domain,
            "memory_types": list(packet.classification.memory_types),
            "scope": packet.classification.scope,
            "tags": list(packet.classification.tags or ()),
            "include_detail": packet.classification.include_detail,
            "rationale": packet.classification.rationale,
        },
        "preferences": packet.preferences,
        "facts": packet.facts,
        "episodic_context": packet.episodic_context,
        "evidence": packet.evidence,
        "token_estimates": {
            "before": packet.before_token_estimate,
            "after": packet.after_token_estimate,
            "budget": packet.token_budget,
            "reduction_percent": packet.token_reduction_percent,
        },
    }


def _tags_to_dict(tags: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(tag.id),
            "memory_id": str(tag.memory_id),
            "tag": tag.tag,
            "status": tag.status,
        }
        for tag in tags
    ]


def _allowed_sensitivities(include_sensitive: bool) -> tuple[str, ...]:
    if include_sensitive:
        _require_sensitive_tools_enabled()
    return ALL_SENSITIVITIES if include_sensitive else DEFAULT_SENSITIVITIES


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _require_mutation_tools_enabled() -> None:
    if not _env_flag(MUTATION_TOOLS_ENV):
        raise PermissionError(
            f"Mutation MCP tools are disabled. Set {MUTATION_TOOLS_ENV}=true to enable them."
        )


def _require_sensitive_tools_enabled() -> None:
    if not _env_flag(SENSITIVE_TOOLS_ENV):
        raise PermissionError(
            f"Sensitive MCP access is disabled. Set {SENSITIVE_TOOLS_ENV}=true to enable it."
        )


def _require_sensitive_echo_allowed(
    sensitivity: str,
    *,
    include_content: bool,
    include_evidence: bool,
) -> None:
    if sensitivity in {"sensitive", "private"} and (include_content or include_evidence):
        _require_sensitive_tools_enabled()


def _bounded_int(name: str, value: int, *, minimum: int, maximum: int) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _validate_text(
    name: str,
    value: str | None,
    *,
    max_chars: int,
    required: bool = False,
) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if required and not value.strip():
        raise ValueError(f"{name} cannot be empty")
    if len(value) > max_chars:
        raise ValueError(f"{name} must be {max_chars} characters or fewer")
    return value


def _validate_json_payload(name: str, value: Any, *, max_chars: int) -> Any:
    if value is None:
        return None
    encoded = json.dumps(value, default=str, sort_keys=True)
    if len(encoded) > max_chars:
        raise ValueError(f"{name} JSON payload must be {max_chars} characters or fewer")
    return value


def _validate_tags(tags: list[str] | None) -> list[str] | None:
    if tags is None:
        return None
    return _validate_string_list(
        "tags",
        tags,
        max_items=MAX_TAGS,
        max_chars=MAX_TAG_CHARS,
    )


def _validate_scope_path(scope_path: list[str] | None) -> list[str] | None:
    if scope_path is None:
        return None
    return _validate_string_list(
        "scope_path",
        scope_path,
        max_items=MAX_SCOPE_PATH_PARTS,
        max_chars=MAX_SCOPE_PATH_PART_CHARS,
    )


def _validate_cache_version(value: str | None) -> str | None:
    return _validate_text("if_cache_version", value, max_chars=2_000)


def _validate_uuid_list(name: str, values: list[str] | None) -> list[str] | None:
    values = _validate_string_list(name, values, max_items=50, max_chars=64)
    if values is None:
        return None
    for value in values:
        UUID(value)
    return values


def _validate_string_list(
    name: str,
    values: list[str] | None,
    *,
    max_items: int,
    max_chars: int,
) -> list[str] | None:
    if values is None:
        return None
    if len(values) > max_items:
        raise ValueError(f"{name} must contain {max_items} items or fewer")
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{name} items must be strings")
        if not value.strip():
            raise ValueError(f"{name} items cannot be empty")
        if len(value) > max_chars:
            raise ValueError(f"{name} items must be {max_chars} characters or fewer")
    return values


def _validate_confidence(value: float) -> float:
    if not isinstance(value, int | float):
        raise ValueError("confidence must be a number")
    value = float(value)
    if value < 0 or value > 1:
        raise ValueError("confidence must be between 0 and 1")
    return value


def _validate_sensitivity(value: str) -> str:
    if value not in VALID_SENSITIVITIES:
        allowed = ", ".join(ALL_SENSITIVITIES)
        raise ValueError(f"sensitivity must be one of: {allowed}")
    return value


def _validate_memory_scope(value: str | None) -> str | None:
    if value is None:
        return None
    if value not in VALID_MEMORY_SCOPES:
        allowed = ", ".join(sorted(VALID_MEMORY_SCOPES))
        raise ValueError(f"memory_scope must be one of: {allowed}")
    return value


def _validate_scope_requirements(
    *,
    memory_scope: str | None,
    workspace: str | None,
    project: str | None,
    component: str | None,
) -> None:
    if memory_scope == WORKSPACE_MEMORY_SCOPE and not workspace:
        raise ValueError("workspace is required when memory_scope is 'workspace'")
    if memory_scope == PROJECT_MEMORY_SCOPE and not project:
        raise ValueError("project is required when memory_scope is 'project'")
    if memory_scope == COMPONENT_MEMORY_SCOPE:
        if not project:
            raise ValueError("project is required when memory_scope is 'component'")
        if not component:
            raise ValueError("component is required when memory_scope is 'component'")


def _scoped_applies_to(
    *,
    applies_to: dict[str, Any] | None,
    memory_scope: str,
    workspace: str | None,
    project: str | None,
    component: str | None,
    topic: str | None,
) -> dict[str, Any]:
    if memory_scope in {COMPONENT_MEMORY_SCOPE, PROJECT_MEMORY_SCOPE, WORKSPACE_MEMORY_SCOPE}:
        applies_to = with_default_scope(applies_to)
    return with_memory_scope(
        applies_to,
        memory_scope=memory_scope,
        workspace=workspace,
        project=project,
        component=component,
        topic=topic,
    )


def _preference_memory_types(domain: str | None) -> tuple[str, ...]:
    if domain == "coding":
        return ("coding_preference",)
    if domain == "entertainment":
        return ("entertainment_preference", "inferred_preference")
    return ("coding_preference", "entertainment_preference", "inferred_preference")


def _domain_scope(domain: str | None) -> str | None:
    if domain in {"coding", "project"}:
        return "development"
    if domain == "entertainment":
        return "entertainment"
    return None


def _domain_profile_request(
    domain: str,
    *,
    person_id: str | None,
    workspace: str | None,
    project: str | None,
    component: str | None,
    topic: str | None,
) -> str:
    parts = [f"Summarize the {domain} profile"]
    if person_id:
        parts.append(f"for person {person_id}")
    if workspace:
        parts.append(f"in workspace {workspace}")
    if project:
        parts.append(f"for project {project}")
    if component:
        parts.append(f"component {component}")
    if topic:
        parts.append(f"topic {topic}")
    return " ".join(parts)


def _domain_profile_applies_to(*, person_id: str | None, project: str | None) -> dict[str, Any] | None:
    if person_id:
        return {"person_id": person_id}
    if project:
        return {"project": project}
    return None


def _parse_uuid(value: str | None) -> UUID | None:
    if value is None:
        return None
    return UUID(value)


def _parse_required_uuid(value: str, field_name: str) -> UUID:
    if not value:
        raise ValueError(f"{field_name} is required")
    return UUID(value)


def _tuple_or_none(values: Sequence[str] | None) -> tuple[str, ...] | None:
    if not values:
        return None
    return tuple(values)


def _format_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
