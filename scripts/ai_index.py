"""Deterministic maintenance helpers for the repository AI index."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Iterable


GENERATED_REGION = "repo-map"
START_MARKER = "<!-- AI-GENERATED:START repo-map -->"
END_MARKER = "<!-- AI-GENERATED:END repo-map -->"
INDEX_PATH = Path(".ai/index.json")
INDEX_FILES = (
    "AGENTS.md",
    "AI_INDEX.md",
    "AI_ARCHITECTURE.md",
    "docs/ai-indexing.md",
)
REVIEW_EVIDENCE_FILES = (*INDEX_FILES, ".ai/index.json")
SENSITIVE_PREFIXES = (
    "src/memory_mcp/",
    "hooks/",
    "migrations/",
)
SENSITIVE_FILES = ("Dockerfile", "docker-compose.yml", "pyproject.toml")

PATH_DESCRIPTIONS = (
    (".memory-mcp/", "Issue readiness and outer-harness execution contracts."),
    ("src/memory_mcp/", "Service package: MCP, persistence, retrieval, authorization, ingestion, and lifecycle features."),
    ("src/memory_mcp/mcp_tools/", "MCP server and public tool definitions."),
    ("src/memory_mcp/auth/", "Trusted-local and remote principal, grant, OIDC, and proxy controls."),
    ("src/memory_mcp/ingest/", "Markdown/wiki parsing, provenance-aware writing, and graph projection."),
    ("src/memory_mcp/retrieval/", "Hybrid retrieval and relationship-aware projection."),
    ("src/memory_mcp/distiller/", "Staged-observation distillation service and worker runner."),
    ("src/memory_mcp/models/", "SQLAlchemy schema and shared persistence types."),
    ("src/memory_mcp/repositories/", "Database repositories for memories, entities, relationships, audit, and staging."),
    ("migrations/", "Alembic migration environment and ordered schema revisions."),
    ("hooks/", "Client-side capture hooks; they must remain bounded and non-blocking."),
    ("scripts/", "Operator utilities, ingestion/backfill helpers, and AI-index commands."),
    ("tests/", "Pytest coverage grouped by service capability and integration boundary."),
    ("docs/", "Canonical operator, architecture, ingestion, retrieval, and workflow documentation."),
    ("client-setups/", "Thin, client-specific connection/setup examples."),
    ("benchmarks/", "Repeatable context-reduction benchmark cases and results."),
    ("docker-compose.yml", "Postgres, MCP gateway, and background-distiller development topology."),
    ("pyproject.toml", "Python packaging, runtime dependencies, and pytest configuration."),
)


def render_repo_map(root: Path) -> str:
    """Render the small, stable generated region from paths that actually exist."""
    rows = [
        f"| `{path}` | {description} |"
        for path, description in PATH_DESCRIPTIONS
        if (root / path).exists()
    ]
    return "\n".join(
        [
            START_MARKER,
            "## Generated Repository Map",
            "",
            "| Path | Responsibility |",
            "|---|---|",
            *rows,
            END_MARKER,
        ]
    )


def replace_generated_region(content: str, replacement: str) -> str:
    """Replace exactly one marked region and leave all human prose intact."""
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL
    )
    if len(pattern.findall(content)) != 1:
        raise ValueError("AI_INDEX.md must contain exactly one repo-map generated region")
    return pattern.sub(replacement, content)


def index_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_regions": [GENERATED_REGION],
        "required_index_files": list(INDEX_FILES),
        "review_evidence_files": list(REVIEW_EVIDENCE_FILES),
        "sensitive_change_prefixes": list(SENSITIVE_PREFIXES),
        "sensitive_change_files": list(SENSITIVE_FILES),
    }


def refresh_index(root: Path) -> None:
    """Refresh only automation-owned index data."""
    index_markdown = root / "AI_INDEX.md"
    updated_markdown = replace_generated_region(
        index_markdown.read_text(encoding="utf-8"), render_repo_map(root)
    )
    index_markdown.write_text(
        updated_markdown,
        encoding="utf-8",
    )
    json_path = root / INDEX_PATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(index_payload(), indent=2) + "\n", encoding="utf-8")


def changed_paths(root: Path, base: str) -> list[str]:
    """Return tracked and untracked paths relevant to the current worktree."""
    diff_result = subprocess.run(
        ["git", "diff", "--name-only", base],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    untracked_result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(
        {
            line.replace("\\", "/")
            for output in (diff_result.stdout, untracked_result.stdout)
            for line in output.splitlines()
            if line
        }
    )


def requires_index_review(paths: Iterable[str]) -> bool:
    return any(
        path.startswith(SENSITIVE_PREFIXES) or path in SENSITIVE_FILES for path in paths
    )


def check_index(root: Path, paths: Iterable[str] = ()) -> list[str]:
    """Return all deterministic index-contract failures without mutating files."""
    errors: list[str] = []
    for relative in INDEX_FILES:
        if not (root / relative).is_file():
            errors.append(f"missing required index file: {relative}")

    index_markdown = root / "AI_INDEX.md"
    if index_markdown.is_file():
        try:
            expected = render_repo_map(root)
            actual = re.search(
                re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
                index_markdown.read_text(encoding="utf-8"),
                re.DOTALL,
            )
            if actual is None:
                errors.append("AI_INDEX.md is missing the repo-map generated region")
            elif actual.group(0) != expected:
                errors.append("AI_INDEX.md repo-map is stale; run ai_index_refresh.py")
        except OSError as exc:
            errors.append(f"cannot read AI_INDEX.md: {exc}")

    json_path = root / INDEX_PATH
    if not json_path.is_file():
        errors.append("missing machine-readable index: .ai/index.json")
    else:
        try:
            if json.loads(json_path.read_text(encoding="utf-8")) != index_payload():
                errors.append(".ai/index.json is stale; run ai_index_refresh.py")
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cannot parse .ai/index.json: {exc}")

    normalized_paths = [path.replace("\\", "/") for path in paths]
    if requires_index_review(normalized_paths) and not any(
        path in REVIEW_EVIDENCE_FILES for path in normalized_paths
    ):
        errors.append(
            "architecture-sensitive changes require an AI index review in the same diff"
        )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="maintain the memory-mcp AI index")
    subparsers = parser.add_subparsers(dest="command", required=True)
    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("--root", type=Path, default=Path.cwd())
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--root", type=Path, default=Path.cwd())
    check_parser.add_argument("--base", default="origin/main")
    check_parser.add_argument("--changed", action="append", default=[])
    args = parser.parse_args()
    root = args.root.resolve()

    if args.command == "refresh":
        refresh_index(root)
        print("AI index refreshed.")
        return

    paths = args.changed or changed_paths(root, args.base)
    errors = check_index(root, paths)
    if errors:
        raise SystemExit("AI index check failed:\n- " + "\n- ".join(errors))
    print("AI index check passed.")


if __name__ == "__main__":
    main()
