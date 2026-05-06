"""Configurable source registry for workspace ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SourceConfig:
    """Configuration for a single documentation source."""

    path: str
    type: str  # "markdown" | "mermaid" | "apim_terraform"
    scope: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        valid_types = {"markdown", "mermaid", "apim_terraform"}
        if self.type not in valid_types:
            raise ValueError(f"Invalid source type {self.type!r}. Must be one of: {valid_types}")


def load_manifest(path: str | Path) -> list[SourceConfig]:
    """Read a YAML manifest file and return a list of SourceConfig entries.

    The manifest format is::

        sources:
          - path: docs/
            type: markdown
            scope:
              workspace: myworkspace
              project: myproject

    Args:
        path: Path to the YAML manifest file.

    Returns:
        List of SourceConfig instances.

    Raises:
        FileNotFoundError: If the manifest file does not exist.
        ValueError: If the manifest is malformed.
    """
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not isinstance(data, dict):
        raise ValueError(f"Manifest must be a YAML mapping, got {type(data).__name__}")

    sources_raw = data.get("sources", [])
    if not isinstance(sources_raw, list):
        raise ValueError("'sources' key must be a list")

    sources: list[SourceConfig] = []
    for i, entry in enumerate(sources_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"Source entry {i} must be a mapping")
        try:
            sources.append(
                SourceConfig(
                    path=str(entry["path"]),
                    type=str(entry["type"]),
                    scope=dict(entry.get("scope") or {}),
                )
            )
        except KeyError as exc:
            raise ValueError(f"Source entry {i} is missing required key: {exc}") from exc

    return sources
