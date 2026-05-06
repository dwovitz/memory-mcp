"""Helpers for hierarchical memory scoping."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

GLOBAL_MEMORY_SCOPE = "global"
WORKSPACE_MEMORY_SCOPE = "workspace"
PROJECT_MEMORY_SCOPE = "project"
REPO_MEMORY_SCOPE = "repo"
COMPONENT_MEMORY_SCOPE = "component"

MEMORY_SCOPE_KEY = "memory_scope"
SCOPE_PATH_KEY = "scope_path"
SCOPE_TYPE_KEY = "scope_type"
WORKSPACE_KEY = "workspace"
REPO_KEY = "repo"
PROJECT_KEY = "project"
COMPONENT_KEY = "component"
TOPIC_KEY = "topic"
VALID_FROM_KEY = "valid_from"
VALID_TO_KEY = "valid_to"
OVERRIDES_MEMORY_IDS_KEY = "overrides_memory_ids"
DEFAULT_DEVELOPMENT_SCOPE = "development"

# Ordered hierarchy from broadest to narrowest scope.
# repo sits between project and component.
_HIERARCHY_KEYS: tuple[str, ...] = (
    WORKSPACE_KEY,
    PROJECT_KEY,
    REPO_KEY,
    COMPONENT_KEY,
    TOPIC_KEY,
)


def hierarchy_layers(
    applies_to: Mapping[str, Any],
    *,
    include_inherited: bool = True,
) -> list[dict[str, Any]]:
    """Return scope layers for ``applies_to``, narrowest first.

    Each layer is a dict of the scope keys present up to that depth.
    When ``repo`` is absent but ``project`` is present, the ``repo`` layer
    implicitly inherits the ``project`` value so callers that predate the
    ``repo`` field still match repo-scoped queries.

    When ``include_inherited`` is False only the most specific (narrowest)
    layer is returned.
    """
    resolved = dict(applies_to)

    # Backward-compat: treat repo == project when repo absent.
    if REPO_KEY not in resolved and PROJECT_KEY in resolved:
        resolved[REPO_KEY] = resolved[PROJECT_KEY]

    layers: list[dict[str, Any]] = []
    accumulated: dict[str, Any] = {}
    for key in _HIERARCHY_KEYS:
        if key in resolved:
            accumulated = {**accumulated, key: resolved[key]}
            layers.append(dict(accumulated))

    # Narrowest first.
    layers.reverse()

    if not include_inherited:
        return layers[:1]
    return layers


def with_memory_scope(
    applies_to: Mapping[str, Any] | None,
    *,
    memory_scope: str,
    workspace: str | None = None,
    repo: str | None = None,
    project: str | None = None,
    component: str | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """Return a copy of applies_to with explicit memory scope metadata."""

    scoped = dict(applies_to or {})
    scoped[MEMORY_SCOPE_KEY] = memory_scope
    if workspace is not None:
        scoped[WORKSPACE_KEY] = workspace
    if project is not None:
        scoped[PROJECT_KEY] = project
    if repo is not None:
        scoped[REPO_KEY] = repo
    if component is not None:
        scoped[COMPONENT_KEY] = component
    if topic is not None:
        scoped[TOPIC_KEY] = topic
    return scoped


def with_default_scope(
    applies_to: Mapping[str, Any] | None,
    *,
    scope: str = DEFAULT_DEVELOPMENT_SCOPE,
) -> dict[str, Any]:
    """Return a copy of applies_to with a default scope when none is set."""

    scoped = dict(applies_to or {})
    scoped.setdefault("scope", scope)
    return scoped


def normalize_scope_path(scope_path: Sequence[str]) -> tuple[str, ...]:
    """Return a cleaned non-empty scope path."""

    normalized = tuple(part.strip() for part in scope_path if isinstance(part, str) and part.strip())
    if not normalized:
        raise ValueError("scope_path must contain at least one non-empty string")
    return normalized


def with_scope_path(
    applies_to: Mapping[str, Any] | None,
    *,
    scope_path: Sequence[str],
    scope_type: str | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> dict[str, Any]:
    """Return a copy of applies_to with generic hierarchical scope metadata."""

    scoped = dict(applies_to or {})
    scoped[SCOPE_PATH_KEY] = list(normalize_scope_path(scope_path))
    if scope_type is not None:
        scoped[SCOPE_TYPE_KEY] = scope_type
    if valid_from is not None:
        scoped[VALID_FROM_KEY] = valid_from
    if valid_to is not None:
        scoped[VALID_TO_KEY] = valid_to
    return scoped


def scope_path_layers(
    scope_path: Sequence[str],
    *,
    include_inherited: bool = True,
) -> list[tuple[str, ...]]:
    """Return direct scope first, followed by parent scope prefixes."""

    normalized = normalize_scope_path(scope_path)
    if not include_inherited:
        return [normalized]
    return [normalized[:index] for index in range(len(normalized), 0, -1)]


def without_applies_to_keys(
    applies_to: Mapping[str, Any] | None,
    *keys: str,
) -> dict[str, Any] | None:
    """Return applies_to without the provided keys."""

    if not applies_to:
        return None
    excluded = set(keys)
    filtered = {key: value for key, value in applies_to.items() if key not in excluded}
    return filtered or None
