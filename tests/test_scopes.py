"""Tests for src/memory_mcp/scopes.py — repo scope layer support."""

from __future__ import annotations

import pytest

from memory_mcp.scopes import (
    COMPONENT_KEY,
    COMPONENT_MEMORY_SCOPE,
    GLOBAL_MEMORY_SCOPE,
    MEMORY_SCOPE_KEY,
    PROJECT_KEY,
    PROJECT_MEMORY_SCOPE,
    REPO_KEY,
    REPO_MEMORY_SCOPE,
    TOPIC_KEY,
    WORKSPACE_KEY,
    WORKSPACE_MEMORY_SCOPE,
    hierarchy_layers,
    normalize_scope_path,
    scope_path_layers,
    with_memory_scope,
    with_scope_path,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_repo_memory_scope_constant_exists() -> None:
    assert REPO_MEMORY_SCOPE == "repo"


def test_repo_key_constant_exists() -> None:
    assert REPO_KEY == "repo"


# ---------------------------------------------------------------------------
# with_memory_scope — repo field
# ---------------------------------------------------------------------------


def test_with_memory_scope_includes_repo() -> None:
    result = with_memory_scope(
        None,
        memory_scope=PROJECT_MEMORY_SCOPE,
        workspace="ai",
        project="memory-mcp",
        repo="memory-mcp",
    )
    assert result[REPO_KEY] == "memory-mcp"
    assert result[PROJECT_KEY] == "memory-mcp"
    assert result[WORKSPACE_KEY] == "ai"


def test_with_memory_scope_repo_absent_when_not_passed() -> None:
    result = with_memory_scope(
        None,
        memory_scope=PROJECT_MEMORY_SCOPE,
        workspace="ai",
        project="memory-mcp",
    )
    assert REPO_KEY not in result


def test_with_memory_scope_preserves_existing_keys() -> None:
    base = {"custom": "value"}
    result = with_memory_scope(
        base,
        memory_scope=GLOBAL_MEMORY_SCOPE,
        repo="my-repo",
    )
    assert result["custom"] == "value"
    assert result[REPO_KEY] == "my-repo"
    assert result[MEMORY_SCOPE_KEY] == GLOBAL_MEMORY_SCOPE


def test_with_memory_scope_all_fields() -> None:
    result = with_memory_scope(
        None,
        memory_scope=COMPONENT_MEMORY_SCOPE,
        workspace="ws",
        project="proj",
        repo="repo-x",
        component="comp",
        topic="topic-y",
    )
    assert result[WORKSPACE_KEY] == "ws"
    assert result[PROJECT_KEY] == "proj"
    assert result[REPO_KEY] == "repo-x"
    assert result[COMPONENT_KEY] == "comp"
    assert result[TOPIC_KEY] == "topic-y"


# ---------------------------------------------------------------------------
# hierarchy_layers
# ---------------------------------------------------------------------------


def test_hierarchy_layers_includes_repo() -> None:
    applies_to = {WORKSPACE_KEY: "ai", PROJECT_KEY: "proj", REPO_KEY: "my-repo"}
    layers = hierarchy_layers(applies_to)
    # All layers should be present
    assert len(layers) == 3
    narrowest = layers[0]
    assert narrowest[REPO_KEY] == "my-repo"


def test_hierarchy_layers_narrowest_first() -> None:
    applies_to = {
        WORKSPACE_KEY: "ai",
        PROJECT_KEY: "proj",
        REPO_KEY: "repo",
        COMPONENT_KEY: "comp",
    }
    layers = hierarchy_layers(applies_to)
    # narrowest layer (index 0) has all four keys
    assert COMPONENT_KEY in layers[0]
    assert REPO_KEY in layers[0]
    # broadest layer (last) has only workspace
    assert layers[-1] == {WORKSPACE_KEY: "ai"}


def test_hierarchy_layers_backward_compat_no_repo() -> None:
    """When repo absent, hierarchy inserts repo == project implicitly."""
    applies_to = {WORKSPACE_KEY: "ai", PROJECT_KEY: "proj"}
    layers = hierarchy_layers(applies_to)

    # The layer set must include a layer that has repo == project
    layers_with_repo = [l for l in layers if REPO_KEY in l]
    assert layers_with_repo, "Expected at least one layer to contain repo key"
    assert layers_with_repo[0][REPO_KEY] == "proj"


def test_hierarchy_layers_backward_compat_project_only() -> None:
    """Project-only callers produce a valid hierarchy including repo layer."""
    applies_to = {PROJECT_KEY: "my-project"}
    layers = hierarchy_layers(applies_to)
    # Should include both project and repo layers
    assert any(REPO_KEY in l for l in layers)
    assert any(PROJECT_KEY in l for l in layers)


def test_hierarchy_layers_include_inherited_false() -> None:
    applies_to = {WORKSPACE_KEY: "ws", PROJECT_KEY: "p", REPO_KEY: "r"}
    layers = hierarchy_layers(applies_to, include_inherited=False)
    assert len(layers) == 1
    # The single layer is the narrowest (repo present)
    assert REPO_KEY in layers[0]


def test_hierarchy_layers_empty() -> None:
    layers = hierarchy_layers({})
    assert layers == []


def test_hierarchy_layers_does_not_mutate_input() -> None:
    original = {PROJECT_KEY: "proj"}
    _ = hierarchy_layers(original)
    assert REPO_KEY not in original


# ---------------------------------------------------------------------------
# scope_path_layers (existing function — regression)
# ---------------------------------------------------------------------------


def test_scope_path_layers_returns_narrowest_first() -> None:
    result = scope_path_layers(["ai", "memory-mcp", "scopes"])
    assert result[0] == ("ai", "memory-mcp", "scopes")
    assert result[-1] == ("ai",)


def test_scope_path_layers_include_inherited_false() -> None:
    result = scope_path_layers(["ai", "memory-mcp"], include_inherited=False)
    assert len(result) == 1
    assert result[0] == ("ai", "memory-mcp")


# ---------------------------------------------------------------------------
# Existing functionality — regression guard
# ---------------------------------------------------------------------------


def test_with_memory_scope_no_repo_still_works() -> None:
    result = with_memory_scope(
        None,
        memory_scope=WORKSPACE_MEMORY_SCOPE,
        workspace="ai",
    )
    assert result[MEMORY_SCOPE_KEY] == WORKSPACE_MEMORY_SCOPE
    assert result[WORKSPACE_KEY] == "ai"
    assert REPO_KEY not in result


def test_normalize_scope_path_strips_blanks() -> None:
    result = normalize_scope_path(["ai", " ", "proj"])
    assert result == ("ai", "proj")


def test_with_scope_path_roundtrip() -> None:
    result = with_scope_path(None, scope_path=["ai", "proj"])
    assert result["scope_path"] == ["ai", "proj"]
