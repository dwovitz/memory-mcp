"""Pluggable extractors for documentation sources."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


def _stable_ingest_key(source_path: str, heading_path: str) -> str:
    """Compute a stable 16-char hex hash from source path and heading path."""
    raw = f"{source_path}::{heading_path}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _make_memory(
    content: str,
    applies_to: dict[str, Any],
    ingest_key: str,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"ingest_key": ingest_key}
    if extra_metadata:
        metadata.update(extra_metadata)
    return {
        "content": content,
        "memory_type": "project_fact",
        "applies_to": dict(applies_to),
        "metadata": metadata,
    }


def extract_markdown_sections(
    file_path: str | Path,
    scope: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract sections from a Markdown file as memory dicts.

    Each ATX heading (``# ...``) starts a new section. The content is the
    heading line plus all text until the next heading of equal or higher level.

    Args:
        file_path: Path to the Markdown file.
        scope: Scope dict (workspace/project/repo/component keys).

    Returns:
        List of memory dicts with keys: content, title, memory_type,
        applies_to, metadata (containing ingest_key).
    """
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    source_str = str(path)

    # Split on ATX headings, capturing level, heading text, and body
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    matches = list(heading_re.finditer(text))

    memories: list[dict[str, Any]] = []
    heading_stack: list[str] = []  # tracks ancestor heading titles

    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()

        # Determine body text (up to next heading)
        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()

        content = f"{match.group(0)}\n\n{body}" if body else match.group(0)

        # Maintain heading stack for stable path
        heading_stack = heading_stack[: level - 1]
        heading_stack.append(title)
        heading_path = " > ".join(heading_stack)

        ingest_key = _stable_ingest_key(source_str, heading_path)
        memories.append(_make_memory(content, scope, ingest_key))

    return memories


def extract_mermaid_nodes(
    file_path: str | Path,
    scope: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract node labels from mermaid code blocks in a Markdown file.

    Finds all ```mermaid ... ``` blocks and extracts unique node labels.
    If no mermaid blocks are found, returns [].

    Args:
        file_path: Path to the Markdown file containing mermaid blocks.
        scope: Scope dict.

    Returns:
        List of memory dicts, one per mermaid block with all node labels
        as content. Empty list if no mermaid blocks found.
    """
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    source_str = str(path)

    # Find all mermaid fenced blocks
    block_re = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
    blocks = list(block_re.finditer(text))

    if not blocks:
        return []

    memories: list[dict[str, Any]] = []

    # Node label patterns: covers common mermaid node syntax
    # e.g. A[Label], B(Label), C{Label}, D>Label], E[(Label)], just words on edges
    node_label_re = re.compile(
        r"""
        (?:
            \w+\[([^\]]+)\]       # A[Label]
            |\w+\(([^)]+)\)       # A(Label) or A((Label))
            |\w+\{([^}]+)\}       # A{Label}
            |\w+>"?([^"\]]+)"?\]  # A>Label]
        )
        """,
        re.VERBOSE,
    )

    for i, block in enumerate(blocks):
        block_content = block.group(1)
        labels = []
        seen: set[str] = set()
        for m in node_label_re.finditer(block_content):
            label = next(g for g in m.groups() if g is not None).strip()
            if label and label not in seen:
                seen.add(label)
                labels.append(label)

        if not labels:
            # Fall back: include raw block content
            labels_text = block_content.strip()
        else:
            labels_text = "\n".join(f"- {lbl}" for lbl in labels)

        heading_path = f"mermaid_block_{i}"
        ingest_key = _stable_ingest_key(source_str, heading_path)
        title = f"Mermaid diagram {i + 1}"
        content = f"Mermaid diagram nodes:\n{labels_text}"
        memories.append(_make_memory(content, scope, ingest_key))

    return memories


def extract_apim_routes(
    file_path: str | Path,
    scope: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract resource and operation blocks from a Terraform (.tf) file.

    Parses ``resource`` blocks (top-level) and extracts their type and name.
    If parsing fails for any reason, returns [].

    Args:
        file_path: Path to the Terraform file.
        scope: Scope dict.

    Returns:
        List of memory dicts, one per resource block. Empty list on failure.
    """
    path = Path(file_path)
    source_str = str(path)

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    # Match resource blocks: resource "type" "name" { ... }
    resource_re = re.compile(
        r'^resource\s+"([^"]+)"\s+"([^"]+)"\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
        re.MULTILINE | re.DOTALL,
    )
    memories: list[dict[str, Any]] = []

    for match in resource_re.finditer(text):
        res_type = match.group(1)
        res_name = match.group(2)
        body = match.group(3).strip()

        title = f"{res_type}.{res_name}"
        content = f'resource "{res_type}" "{res_name}" {{\n{body}\n}}'
        heading_path = title
        ingest_key = _stable_ingest_key(source_str, heading_path)
        memories.append(_make_memory(content, scope, ingest_key))

    return memories
