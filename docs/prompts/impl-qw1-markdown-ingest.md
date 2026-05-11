# Implementation Prompt — QW1 Markdown Ingest Script

**Model:** Sonnet
**Estimated effort:** 2–4 hrs (may be less — ingest package already exists)
**Branch:** `feat/qw1-markdown-ingest`

## Context

Quick Win 1 from the upgrades plan: a script that walks a workspace directory for
`*.md` and `*.mdc` files, splits them by heading, and writes one memory per
heading block to memory-mcp with `workspace=<workspace>` scope.

The ingest package (`src/memory_mcp/ingest/`) and `scripts/ingest_workspace.py`
already exist on main. This track checks if heading-level markdown ingestion is
already functional and adds it if not.

## Step 1: Audit what exists

```bash
python -c "import ast; ast.parse(open('scripts/ingest_workspace.py').read()); print('syntax ok')"
pytest tests/ingest/ -v
```

Read `src/memory_mcp/ingest/parser.py` and `scripts/ingest_workspace.py`.
Check: does the parser split markdown by heading and produce one memory per section?
If yes, skip to Step 4 (integration test).

## Step 2: Add heading-level markdown parser (if missing)

In `src/memory_mcp/ingest/parser.py`, add or extend `parse_markdown_headings`:

```python
import re
from dataclasses import dataclass
from pathlib import Path

@dataclass
class MarkdownSection:
    heading: str
    level: int
    body: str
    source_path: str
    heading_path: list[str]  # breadcrumb of ancestor headings


def parse_markdown_headings(path: Path) -> list[MarkdownSection]:
    """Split a markdown file into one section per heading."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    sections: list[MarkdownSection] = []
    heading_stack: list[tuple[int, str]] = []
    current_body: list[str] = []
    current_heading = ""
    current_level = 0

    def flush():
        if current_heading:
            breadcrumb = [h for _, h in heading_stack[:-1]]
            sections.append(MarkdownSection(
                heading=current_heading,
                level=current_level,
                body="".join(current_body).strip(),
                source_path=str(path),
                heading_path=breadcrumb,
            ))

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush()
            current_level = len(m.group(1))
            current_heading = m.group(2).strip()
            current_body = []
            # trim stack to current level
            heading_stack = [(lvl, h) for lvl, h in heading_stack if lvl < current_level]
            heading_stack.append((current_level, current_heading))
        else:
            current_body.append(line)

    flush()
    return sections
```

## Step 3: Add/extend ingest script

Create `scripts/ingest_markdown_workspace.py`:

```python
#!/usr/bin/env python
"""Ingest markdown workspace docs into memory-mcp.

Usage:
  python scripts/ingest_markdown_workspace.py \
    --workspace ucx-root \
    --dir /path/to/workspace \
    --glob "**/*.md" "**/*.mdc"
"""
import argparse
import hashlib
from pathlib import Path

from memory_mcp.db import session_scope
from memory_mcp.ingest.parser import parse_markdown_headings
from memory_mcp.ingest.writer import IngestWriter


def ingest_key(source_path: str, heading_path: list[str], heading: str) -> str:
    raw = "|".join([source_path] + heading_path + [heading])
    return "md:" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def run(workspace: str, root: Path, globs: list[str]) -> None:
    files: list[Path] = []
    for pattern in globs:
        files.extend(root.glob(pattern))
    files = sorted(set(files))
    print(f"Found {len(files)} files")

    with session_scope() as session:
        writer = IngestWriter(session)
        written = skipped = 0
        for path in files:
            sections = parse_markdown_headings(path)
            for sec in sections:
                if not sec.body:
                    continue
                content = f"# {sec.heading}\n\n{sec.body}"
                key = ingest_key(sec.source_path, sec.heading_path, sec.heading)
                result = writer.upsert(
                    content=content,
                    memory_type="project_fact",
                    memory_scope="workspace",
                    applies_to={"workspace": workspace},
                    tags=["ingest:markdown", f"source:{Path(sec.source_path).name}"],
                    metadata={"ingest_key": key, "source_path": sec.source_path,
                              "heading": sec.heading},
                )
                if result == "created":
                    written += 1
                else:
                    skipped += 1
        session.commit()
    print(f"Done: {written} written, {skipped} unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--glob", nargs="+", default=["**/*.md", "**/*.mdc"])
    args = parser.parse_args()
    run(args.workspace, args.dir, args.glob)
```

## Step 4: Write tests

```python
# tests/ingest/test_markdown_ingest.py
from pathlib import Path
import tempfile
from memory_mcp.ingest.parser import parse_markdown_headings


def test_parse_single_heading():
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# Title\n\nSome content here.\n")
        p = Path(f.name)
    sections = parse_markdown_headings(p)
    assert len(sections) == 1
    assert sections[0].heading == "Title"
    assert "Some content here" in sections[0].body


def test_parse_multiple_headings():
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# H1\n\nBody1.\n\n## H2\n\nBody2.\n")
        p = Path(f.name)
    sections = parse_markdown_headings(p)
    assert len(sections) == 2
    assert sections[0].heading == "H1"
    assert sections[1].heading == "H2"
    assert sections[1].heading_path == ["H1"]


def test_empty_body_sections_have_empty_body_string():
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# H1\n\n## H2\n\nBody.\n")
        p = Path(f.name)
    sections = parse_markdown_headings(p)
    assert sections[0].body == ""
    assert sections[1].body == "Body."
```

## Step 5: Run tests

```bash
pytest tests/ingest/ -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/qw1-markdown-ingest --no-ff -m "feat: add QW1 markdown workspace ingest script"
git push origin main
```

## Handoff prompt for Track 4

```
Continue memory-mcp roadmap. Track 3 (QW1 markdown ingest) is complete and merged to main.
Next: Track 4 — read docs/prompts/impl-p1-entity-graph.md and implement it.
Branch off main as feat/p1-entity-graph. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 3 status from ⬜ to ✅ before starting Track 4.
```
