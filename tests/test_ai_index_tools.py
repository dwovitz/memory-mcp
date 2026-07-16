from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ai_index import (  # noqa: E402
    END_MARKER,
    START_MARKER,
    check_index,
    changed_paths,
    index_payload,
    refresh_index,
)


def _seed_index_root(root: Path) -> None:
    (root / "docs").mkdir()
    (root / ".ai").mkdir()
    (root / "src" / "memory_mcp" / "mcp_tools").mkdir(parents=True)
    for path in ("AGENTS.md", "AI_ARCHITECTURE.md", "docs/ai-indexing.md"):
        (root / path).write_text("human-authored\n", encoding="utf-8")
    (root / "AI_INDEX.md").write_text(
        "before\n" + START_MARKER + "\nstale\n" + END_MARKER + "\nafter\n",
        encoding="utf-8",
    )
    (root / ".ai/index.json").write_text(
        json.dumps(index_payload()), encoding="utf-8"
    )


def test_refresh_only_rewrites_the_marked_region(tmp_path: Path) -> None:
    _seed_index_root(tmp_path)

    refresh_index(tmp_path)

    content = (tmp_path / "AI_INDEX.md").read_text(encoding="utf-8")
    assert content.startswith("before\n")
    assert content.endswith("after\n")
    assert "| `src/memory_mcp/mcp_tools/` |" in content
    assert check_index(tmp_path, ["AI_INDEX.md", ".ai/index.json"]) == []


def test_check_requires_index_review_for_sensitive_changes(tmp_path: Path) -> None:
    _seed_index_root(tmp_path)
    refresh_index(tmp_path)

    for changed_path in (
        "src/memory_mcp/mcp_tools/server.py",
        "src/memory_mcp/scopes.py",
        "src/memory_mcp/distiller/service.py",
    ):
        assert check_index(tmp_path, [changed_path]) == [
            "architecture-sensitive changes require an AI index review in the same diff"
        ]


def test_check_reports_stale_generated_content(tmp_path: Path) -> None:
    _seed_index_root(tmp_path)
    refresh_index(tmp_path)
    index = tmp_path / "AI_INDEX.md"
    index.write_text(
        index.read_text(encoding="utf-8").replace("src/memory_mcp/", "stale/", 1),
        encoding="utf-8",
    )

    assert "AI_INDEX.md repo-map is stale; run ai_index_refresh.py" in check_index(
        tmp_path, ["AI_INDEX.md"]
    )


def test_changed_paths_includes_untracked_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, check=True
    )
    (tmp_path / "README.md").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True)
    untracked = tmp_path / "src" / "memory_mcp" / "new_component.py"
    untracked.parent.mkdir(parents=True)
    untracked.write_text("pass\n", encoding="utf-8")

    assert changed_paths(tmp_path, "HEAD") == ["src/memory_mcp/new_component.py"]
