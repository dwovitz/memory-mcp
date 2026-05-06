#!/usr/bin/env python
"""CLI script to ingest documentation files into memory-mcp.

Usage::

    python scripts/ingest_workspace.py --manifest ingest.manifest.yaml.example
    python scripts/ingest_workspace.py --manifest ingest.manifest.yaml.example --dry-run
    python scripts/ingest_workspace.py --manifest ingest.manifest.yaml.example --strict
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest documentation files into memory-mcp.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--manifest",
        required=True,
        metavar="PATH",
        help="Path to the YAML manifest file listing sources.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would be written without making any changes.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Abort on any parser error (default: skip failed sources).",
    )
    return parser


def _collect_source_files(source_path: str, manifest_dir: Path) -> list[Path]:
    """Resolve glob/dir/file paths relative to the manifest directory."""
    base = manifest_dir / source_path
    if base.is_dir():
        # Collect all files recursively
        return sorted(f for f in base.rglob("*") if f.is_file())
    elif base.is_file():
        return [base]
    else:
        # Try glob relative to manifest dir
        matched = sorted(manifest_dir.glob(source_path))
        return [p for p in matched if p.is_file()]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest).resolve()

    # Import here so the script is importable without a DB connection
    from memory_mcp.ingest.sources import load_manifest
    from memory_mcp.ingest.parser import (
        extract_markdown_sections,
        extract_mermaid_nodes,
        extract_apim_routes,
    )

    try:
        sources = load_manifest(manifest_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    manifest_dir = manifest_path.parent

    parser_map = {
        "markdown": extract_markdown_sections,
        "mermaid": extract_mermaid_nodes,
        "apim_terraform": extract_apim_routes,
    }

    all_memories: list[dict] = []
    files_scanned = 0
    errors: list[str] = []

    for source in sources:
        files = _collect_source_files(source.path, manifest_dir)
        if not files:
            msg = f"WARNING: No files found for source path: {source.path}"
            print(msg)
            continue

        extract_fn = parser_map.get(source.type)
        if extract_fn is None:
            msg = f"ERROR: Unknown source type: {source.type}"
            if args.strict:
                print(msg, file=sys.stderr)
                return 1
            errors.append(msg)
            continue

        for file_path in files:
            files_scanned += 1
            try:
                memories = extract_fn(file_path, source.scope)
                all_memories.extend(memories)
            except Exception as exc:  # noqa: BLE001
                msg = f"ERROR parsing {file_path}: {exc}"
                if args.strict:
                    print(msg, file=sys.stderr)
                    return 1
                errors.append(msg)

    print(f"\nFiles scanned: {files_scanned}")
    print(f"Memories extracted: {len(all_memories)}")

    if errors:
        print(f"Errors: {len(errors)}")
        for err in errors:
            print(f"  {err}")

    if args.dry_run:
        print("\n[DRY RUN] Would write the following memories:")
        for i, mem in enumerate(all_memories, 1):
            key = mem["metadata"].get("ingest_key", "?")
            title = mem.get("title", "untitled")
            applies_to = mem.get("applies_to", {})
            print(f"  {i:3d}. [{key}] {title!r}  scope={applies_to}")
        print("\n[DRY RUN] No changes written.")
        return 0

    # Real write — requires DB connection
    from memory_mcp.db.session import get_session  # type: ignore[import]
    from memory_mcp.services.memory_service import MemoryService
    from memory_mcp.ingest.writer import IngestWriter

    try:
        with get_session() as session:
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


if __name__ == "__main__":
    sys.exit(main())
