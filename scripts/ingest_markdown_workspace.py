#!/usr/bin/env python
"""Ingest markdown workspace docs into memory-mcp by heading section.

Usage::

    python scripts/ingest_markdown_workspace.py \\
        --workspace my-workspace \\
        --dir /path/to/docs \\
        --glob "**/*.md" "**/*.mdc"

Each ATX heading (# / ## / ###) becomes one memory entry scoped to the workspace.
Re-runs are idempotent: existing memories with matching ingest_key are updated
only when content changes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def run(workspace: str, root: Path, globs: list[str], dry_run: bool = False) -> int:
    from memory_mcp.ingest.parser import extract_markdown_sections

    files: list[Path] = []
    for pattern in globs:
        files.extend(root.glob(pattern))
    files = sorted(set(files))
    print(f"Found {len(files)} files under {root}")

    scope = {"workspace": workspace}
    all_memories: list[dict] = []
    for path in files:
        sections = extract_markdown_sections(path, scope)
        all_memories.extend(sections)

    print(f"Extracted {len(all_memories)} sections")

    if dry_run:
        print("\n[DRY RUN] Would write:")
        for i, mem in enumerate(all_memories, 1):
            key = mem["metadata"].get("ingest_key", "?")
            snippet = mem["content"][:60].replace("\n", " ")
            print(f"  {i:3d}. [{key}] {snippet!r}")
        print("\n[DRY RUN] No changes written.")
        return 0

    from memory_mcp.db import session_scope
    from memory_mcp.ingest.writer import IngestWriter
    from memory_mcp.services.memory_service import MemoryService

    try:
        with session_scope() as session:
            service = MemoryService(session)
            writer = IngestWriter(service)
            result = writer.upsert_memories(all_memories)
            session.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR writing to DB: {exc}", file=sys.stderr)
        return 1

    print(f"\nResult:")
    print(f"  Created: {result['created']}")
    print(f"  Updated: {result['updated']}")
    print(f"  Skipped: {result['skipped']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest markdown docs into memory-mcp by heading.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--workspace", required=True, help="Workspace name for memory scope.")
    parser.add_argument("--dir", required=True, type=Path, help="Root directory to scan.")
    parser.add_argument(
        "--glob",
        nargs="+",
        default=["**/*.md", "**/*.mdc"],
        help="Glob patterns relative to --dir (default: **/*.md **/*.mdc).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print without writing.")
    args = parser.parse_args(argv)

    if not args.dir.is_dir():
        print(f"ERROR: --dir {args.dir} is not a directory", file=sys.stderr)
        return 1

    return run(args.workspace, args.dir, args.glob, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
