"""Data models for local memory-mcp plugin packages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PluginOutput:
    source: Path
    target: str


@dataclass(frozen=True)
class PluginClientTarget:
    name: str
    outputs: tuple[PluginOutput, ...]


@dataclass(frozen=True)
class PluginHook:
    event: str
    source: Path


@dataclass(frozen=True)
class PluginManifest:
    root: Path
    schema_version: str
    id: str
    display_name: str
    description: str
    version: str
    min_memory_mcp_version: str
    update_channel: str
    category: str
    client_targets: dict[str, PluginClientTarget]
    hooks: tuple[PluginHook, ...]
    server_modes: tuple[str, ...]


@dataclass(frozen=True)
class MarketplaceEntry:
    name: str
    path: Path


@dataclass(frozen=True)
class Marketplace:
    name: str
    display_name: str
    plugins: tuple[MarketplaceEntry, ...]
