#!/usr/bin/env python
"""Ingest a local file-based wiki into memory-mcp as searchable projections.

The wiki stays canonical; memory-mcp stores derived, provenance-stamped
projections. Re-runs are idempotent, changed sections supersede prior records,
and sections or files removed from the wiki are archived as stale projections.

Usage::

    python scripts/ingest_wiki.py \\
        --collection home-wiki \\
        --root /path/to/wiki \\
        --workspace ai --project memory-mcp \\
        --sensitivity private

Wiki content is treated as private by default, so derived chunks and
embeddings are classified as private data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def run(
    *,
    collection: str,
    root: Path,
    scope: dict[str, str],
    sensitivity: str,
    globs: list[str],
    dry_run: bool = False,
) -> int:
    from memory_mcp.ingest.wiki import WikiSource, build_wiki_records

    source = WikiSource(
        root=root,
        collection=collection,
        scope=scope,
        sensitivity=sensitivity,
        globs=tuple(globs),
    )
    files = source.resolve_files()
    print(f"Found {len(files)} wiki files under {root} (collection={collection!r})")

    if dry_run:
        total = 0
        for path in files:
            records = build_wiki_records(
                path,
                collection=collection,
                scope=scope,
                sensitivity=sensitivity,
                root=root,
            )
            total += len(records)
            for rec in records:
                src = rec["metadata"]["source"]
                print(f"  [{rec['metadata']['ingest_key'][:8]}] {src['section']}")
        print(f"\n[DRY RUN] Would project {total} records. No changes written.")
        return 0

    from memory_mcp.db import session_scope
    from memory_mcp.ingest.wiki import WikiIngestService
    from memory_mcp.services.memory_service import MemoryService

    try:
        with session_scope() as session:
            service = MemoryService(session)
            ingest = WikiIngestService(service)
            result = ingest.ingest([source])
            session.commit()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR writing to DB: {exc}", file=sys.stderr)
        return 1

    print("\nResult:")
    print(f"  Created:  {result.created}")
    print(f"  Updated:  {result.updated}")
    print(f"  Skipped:  {result.skipped}")
    print(f"  Archived: {result.archived}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest a local wiki into memory-mcp as searchable projections.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--collection", required=True, help="Stable wiki collection id.")
    parser.add_argument("--root", required=True, type=Path, help="Wiki root directory or file.")
    parser.add_argument("--workspace", help="Workspace scope.")
    parser.add_argument("--project", help="Project scope.")
    parser.add_argument("--repo", help="Repo scope.")
    parser.add_argument("--component", help="Component scope.")
    parser.add_argument(
        "--sensitivity",
        default="private",
        choices=["normal", "sensitive", "private"],
        help="Sensitivity for derived records (default: private).",
    )
    parser.add_argument(
        "--glob",
        nargs="+",
        default=["**/*.md", "**/*.markdown"],
        help="Glob patterns relative to --root.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print without writing.")
    args = parser.parse_args(argv)

    if not args.root.exists():
        print(f"ERROR: --root {args.root} does not exist", file=sys.stderr)
        return 1

    scope = {
        k: v
        for k, v in {
            "workspace": args.workspace,
            "project": args.project,
            "repo": args.repo,
            "component": args.component,
        }.items()
        if v
    }

    return run(
        collection=args.collection,
        root=args.root,
        scope=scope,
        sensitivity=args.sensitivity,
        globs=args.glob,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
