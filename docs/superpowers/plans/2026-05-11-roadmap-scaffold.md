# Roadmap Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute Track 0 of the memory-mcp completion roadmap — merge the current branch to main, archive stale branches, create `docs/prompts/ROADMAP.md`, and write all 12 cold-start implementation prompt files.

**Architecture:** No application code changes in this plan. All output is documentation files in `docs/prompts/`. Each prompt file is a self-contained cold-start implementation guide for one feature track. After this plan is complete, each track is executed independently by loading its prompt file in a fresh session.

**Tech Stack:** git, markdown. The working directory is the memory-mcp repo root.

---

## What Is Already On `main` (Do Not Re-implement)

- Migrations 0001–0006 (including HNSW embedding index)
- `src/memory_mcp/embeddings/` (provider, local_provider, service, config)
- `scripts/backfill_embeddings.py`, `scripts/ingest_workspace.py`
- `src/memory_mcp/ingest/` (parser, sources, writer)
- `src/memory_mcp/repositories/entities.py`, `repositories/relationships.py`
- QW2 (`repo` param), QW4 (`search_entities` tool), QW5 (scope_path docs), QW6 (secrets guard)
- `tests/test_hybrid_retrieval_embedding.py`, `tests/ingest/`

---

## Task 1: Track 0 — Branch Cleanup and Merge

**Files:** none (git operations only)

- [ ] **Step 1: Merge feat/auto-capture-distillation to main**

```bash
git checkout main
git merge feat/auto-capture-distillation --no-ff -m "docs(plans): merge auto-capture-distillation plan to main"
```

Expected: fast-forward or merge commit with the plan doc `docs/superpowers/plans/2026-05-07-auto-capture-distillation.md`.

- [ ] **Step 2: Verify codex branches are behind main (no changes to lose)**

```bash
git log main..codex/outline-benchmark-runner --oneline
git log main..codex/source-read-contract-client-setups --oneline
```

Expected: empty output (both branches are fully behind main). If non-empty, stop and investigate before proceeding.

- [ ] **Step 3: Delete stale local codex branches**

```bash
git branch -d codex/outline-benchmark-runner
git branch -d codex/source-read-contract-client-setups
```

- [ ] **Step 4: Verify main is clean**

```bash
git status
git log --oneline -5
```

Expected: clean working tree on main.

---

## Task 2: Create ROADMAP.md

**Files:**
- Create: `docs/prompts/ROADMAP.md`

- [ ] **Step 1: Create the file**

```markdown
# memory-mcp Completion Roadmap

Track status is updated after each merge to main.
Each prompt file is a cold-start implementation guide — load it in a fresh session.

## Handoff Prompt Template

Paste this into the next session after completing a track:

```
Continue memory-mcp roadmap. Track <N> (<name>) is complete and merged to main.
Next: Track <N+1> — read docs/prompts/<prompt-file> and implement it.
Branch off main as feat/<slug>. Use <model>.
Check docs/prompts/ROADMAP.md for current status before starting.
```

## Tracks

| # | Track | Prompt file | Branch | Model | Effort | Status |
|---|---|---|---|---|---|---|
| 0 | Branch cleanup + scaffold | *(this session)* | main | — | 15 min | ✅ |
| 1 | Auto-capture + distillation | [impl-auto-capture.md](impl-auto-capture.md) | `feat/auto-capture-distillation` | Sonnet | 1–2 days | ⬜ |
| 2 | Verify / complete semantic retrieval | [impl-semantic-retrieval.md](impl-semantic-retrieval.md) | `feat/p0-semantic-retrieval` | Sonnet | 2–4 hrs | ⬜ |
| 3 | QW1 markdown ingest script | [impl-qw1-markdown-ingest.md](impl-qw1-markdown-ingest.md) | `feat/qw1-markdown-ingest` | Sonnet | 2–4 hrs | ⬜ |
| 4 | P1 entity graph MCP tools | [impl-p1-entity-graph.md](impl-p1-entity-graph.md) | `feat/p1-entity-graph` | Sonnet | 4–8 hrs | ⬜ |
| 5 | P1 code citations + QW3 cited_path | [impl-p1-code-citations.md](impl-p1-code-citations.md) | `feat/p1-code-citations` | Sonnet | 4–6 hrs | ⬜ |
| 6 | P1 classifier upgrade | [impl-p1-classifier.md](impl-p1-classifier.md) | `feat/p1-classifier` | Sonnet | 4–6 hrs | ⬜ |
| 7 | P2 event-flow memory types | [impl-p2-event-flow.md](impl-p2-event-flow.md) | `feat/p2-event-flow` | Sonnet | 3–5 hrs | ⬜ |
| 8 | P2 context packet diagnostics | [impl-p2-packet-diagnostics.md](impl-p2-packet-diagnostics.md) | `feat/p2-packet-diagnostics` | Sonnet | 3–4 hrs | ⬜ |
| 9 | P2 code graph import tool | [impl-p2-code-graph-import.md](impl-p2-code-graph-import.md) | `feat/p2-code-graph-import` | Sonnet | 3–4 hrs | ⬜ |
| 10 | P2 multi-repo benchmark harness | [impl-p2-benchmarks.md](impl-p2-benchmarks.md) | `feat/p2-benchmarks` | Sonnet | 1 day | ⬜ |
| 11 | P3 client hook pack | [impl-p3-hook-pack.md](impl-p3-hook-pack.md) | `feat/p3-hook-pack` | Haiku | 2–4 hrs | ⬜ |
| 12 | P3 hosted mode hardening | [impl-p3-hosted-mode.md](impl-p3-hosted-mode.md) | `feat/p3-hosted-mode` | Sonnet | 4–8 hrs | ⬜ |

## Sequencing Constraints

- Track 6 (classifier) requires Track 4 (entity graph) to be merged first.
- Track 5 (code citations) must precede QW3 — they are bundled.
- Track 8 (packet diagnostics) benefits from Track 6 being done first.
- Track 10 (benchmarks) should run after Tracks 2, 4, 5, 6 are merged.
- Tracks 3, 4, 5 are independent and can be parallelized.
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/ROADMAP.md
git commit -m "docs(roadmap): add completion roadmap tracker"
```

---

## Task 3: Create impl-auto-capture.md

**Files:**
- Create: `docs/prompts/impl-auto-capture.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — Auto-Capture + Distillation

**Model:** Sonnet
**Estimated effort:** 1–2 days
**Branch:** `feat/auto-capture-distillation`

## Context

Adds hook-driven auto-capture of Claude Code session events into a Postgres-backed
staging queue, with a background distiller that compresses raw observations into
typed scoped memories using model-routed Claude calls. Surfaces compressed context
automatically on UserPromptSubmit.

The complete implementation plan already exists:
`docs/superpowers/plans/2026-05-07-auto-capture-distillation.md`

## Instructions

1. Read `docs/superpowers/plans/2026-05-07-auto-capture-distillation.md` in full.
2. Use `superpowers:subagent-driven-development` or `superpowers:executing-plans`
   to implement it task-by-task exactly as written.
3. Run `pytest` after each task. Fix failures before moving on.
4. Run `alembic upgrade head` after the migration task.

## Key files (from the plan)

**Create:**
- `migrations/versions/0010_staging_observations.py`
- `src/memory_mcp/models/staging.py`
- `src/memory_mcp/repositories/staging.py`
- `src/memory_mcp/distiller/__init__.py`
- `src/memory_mcp/distiller/router.py`
- `src/memory_mcp/distiller/prompts.py`
- `src/memory_mcp/distiller/service.py`
- `src/memory_mcp/distiller/runner.py`
- `hooks/post_tool_use.py`
- `hooks/user_prompt_submit.py`
- `hooks/session_start.py`
- `hooks/session_end.py`
- `hooks/_client.py`
- `tests/test_staging_repository.py`
- `tests/distiller/test_router.py`
- `tests/distiller/test_service.py`
- `tests/hooks/test_post_tool_use.py`
- `tests/hooks/test_user_prompt_submit.py`
- `docs/auto_capture.md`

**Modify:**
- `src/memory_mcp/mcp_tools/server.py` — add `enqueue_observation`, `get_memory_by_id`
- `src/memory_mcp/models/__init__.py` — export `StagingObservation`
- `docker-compose.yml` — add `distiller` service
- `pyproject.toml` — add `anthropic` dependency
- `README.md` — link to `docs/auto_capture.md`

## Verification

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_staging_repository.py tests/distiller/ tests/hooks/ -v
alembic upgrade head
```

## Merge

```bash
git checkout main
git merge feat/auto-capture-distillation --no-ff -m "feat: add auto-capture and distillation pipeline"
git push origin main
```

## Handoff prompt for Track 2

```
Continue memory-mcp roadmap. Track 1 (auto-capture + distillation) is complete and merged to main.
Next: Track 2 — read docs/prompts/impl-semantic-retrieval.md and implement it.
Branch off main as feat/p0-semantic-retrieval. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 1 status from ⬜ to ✅ before starting Track 2.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-auto-capture.md
git commit -m "docs(prompts): add Track 1 auto-capture implementation prompt"
```

---

## Task 4: Create impl-semantic-retrieval.md

**Files:**
- Create: `docs/prompts/impl-semantic-retrieval.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — Verify / Complete P0 Semantic Retrieval

**Model:** Sonnet
**Estimated effort:** 2–4 hrs (likely much less — most is already done)
**Branch:** `feat/p0-semantic-retrieval`

## Context

The embedding pipeline was partially implemented in a prior session. Migration `0006`
(HNSW index), `scripts/backfill_embeddings.py`, and `src/memory_mcp/embeddings/`
are all on main. This track verifies the hybrid retrieval blend is wired up correctly
and fills any gaps.

## Step 1: Audit before coding

Run these checks first. If all pass, this track may need zero code changes.

```bash
# 1. Confirm migration 0006 ran
python -c "
from memory_mcp.db import session_scope
from sqlalchemy import text
with session_scope() as s:
    r = s.execute(text(\"SELECT indexname FROM pg_indexes WHERE tablename='memories' AND indexname LIKE '%embedding%'\")).fetchall()
    print('Embedding indexes:', r)
"

# 2. Run embedding tests
pytest tests/embeddings/ tests/test_hybrid_retrieval_embedding.py -v

# 3. Check embedding config
python -c "from memory_mcp.embeddings.config import EmbeddingConfig; c = EmbeddingConfig(); print('enabled:', c.enabled, 'model:', c.model)"
```

## Step 2: Identify gaps

Read `src/memory_mcp/retrieval/service.py` and check:

1. Does `HybridRetrievalService.search_memories` call the embedding service when
   `text_query` is present?
2. Is there a hybrid score blend? Target weights: `0.35*vector + 0.35*text + 0.2*confidence + 0.1*recency`.
3. Is there a graceful fallback to FTS-only when embeddings are disabled or unavailable?

## Step 3: Implement missing pieces

Only implement what the audit reveals is missing. Common gaps:

**Gap A — Hybrid blend not wired:**
In `HybridRetrievalService.search_memories`, after FTS retrieval, compute query
embedding via `EmbeddingService.embed(text_query)` and re-rank:

```python
# After FTS results are fetched:
if text_query and self._embedding_service.is_available():
    try:
        query_vec = self._embedding_service.embed(text_query)
        for result in results:
            if result.memory.embedding is not None:
                vec_score = cosine_similarity(query_vec, result.memory.embedding)
                result.rank_score = (
                    0.35 * vec_score
                    + 0.35 * result.text_rank
                    + 0.20 * result.confidence_score
                    + 0.10 * result.recency_score
                )
    except Exception:
        logger.warning("vector re-rank failed, using text rank only")
```

**Gap B — MEMORY_MCP_EMBEDDING_ENABLED not checked:**
Wrap embedding calls behind `EmbeddingConfig().enabled` so the server starts
cleanly without a local model.

**Gap C — Backfill script not connected to ingest:**
If `IngestWriter` does not call `EmbeddingService.embed` on new memories, add it.
Check `src/memory_mcp/ingest/writer.py` for the lazy embed call.

## Step 4: Write or update tests

If you added code in Step 3, add a test:

```python
# tests/test_hybrid_retrieval_embedding.py — add or extend
def test_hybrid_blend_degrades_gracefully_when_embedding_disabled(db_session):
    """FTS-only path must work when embedding is off."""
    with patch("memory_mcp.embeddings.config.EmbeddingConfig.enabled", False):
        svc = HybridRetrievalService(db_session)
        results = svc.search_memories(text_query="test query", limit=5)
        assert isinstance(results, list)
```

## Step 5: Run full test suite

```bash
pytest -v
```

## Step 6: If no gaps found

If audit passes and tests are green, this track is complete with no code changes.
Still create the branch, add a one-line ROADMAP.md update, and merge:

```bash
git checkout -b feat/p0-semantic-retrieval
# Update ROADMAP.md: Track 2 ⬜ → ✅
git add docs/prompts/ROADMAP.md
git commit -m "docs(roadmap): mark Track 2 semantic retrieval verified"
```

## Merge

```bash
git checkout main
git merge feat/p0-semantic-retrieval --no-ff -m "feat: verify and complete P0 semantic retrieval"
git push origin main
```

## Handoff prompt for Track 3

```
Continue memory-mcp roadmap. Track 2 (semantic retrieval) is complete and merged to main.
Next: Track 3 — read docs/prompts/impl-qw1-markdown-ingest.md and implement it.
Branch off main as feat/qw1-markdown-ingest. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 2 status from ⬜ to ✅ before starting Track 3.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-semantic-retrieval.md
git commit -m "docs(prompts): add Track 2 semantic retrieval prompt"
```

---

## Task 5: Create impl-qw1-markdown-ingest.md

**Files:**
- Create: `docs/prompts/impl-qw1-markdown-ingest.md`

- [ ] **Step 1: Create the file**

```markdown
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
# Check if ingest_workspace.py already handles markdown headings
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

In `scripts/ingest_workspace.py` or a new `scripts/ingest_markdown_workspace.py`,
add a CLI that accepts `--workspace`, `--dir`, and `--glob` (default `**/*.md,**/*.mdc`):

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


def test_empty_body_sections_skipped():
    """Headings with no body produce a section with empty body string."""
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# H1\n\n## H2\n\nBody.\n")
        p = Path(f.name)
    sections = parse_markdown_headings(p)
    # H1 has no body — body is empty string
    assert sections[0].body == ""
    assert sections[1].body == "Body."
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/ingest/test_markdown_ingest.py -v
```

Expected: all pass.

- [ ] **Step 3: Run full test suite**

```bash
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
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-qw1-markdown-ingest.md
git commit -m "docs(prompts): add Track 3 QW1 markdown ingest prompt"
```

---

## Task 6: Create impl-p1-entity-graph.md

**Files:**
- Create: `docs/prompts/impl-p1-entity-graph.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — P1 Entity Graph MCP Tools

**Model:** Sonnet
**Estimated effort:** 4–8 hrs
**Branch:** `feat/p1-entity-graph`

## Context

`Entity` and `Relationship` tables and repositories already exist on main
(`src/memory_mcp/repositories/entities.py`, `repositories/relationships.py`).
`search_entities` is already an MCP tool (QW4). This track adds four more MCP tools:
`upsert_entity`, `link_entities`, `traverse_entity_graph`, and `get_related_memories`.

## Relevant files

- Modify: `src/memory_mcp/mcp_tools/server.py` — add 4 new tools
- Modify: `src/memory_mcp/retrieval/service.py` — add graph traversal helpers
- Modify: `src/memory_mcp/repositories/entities.py` — add upsert + traversal queries
- Modify: `src/memory_mcp/repositories/relationships.py` — add link + neighbor queries
- Test: `tests/test_entity_graph_tools.py` (new)

## Step 1: Read existing code first

Before writing anything, read:
- `src/memory_mcp/repositories/entities.py` — understand Entity model and existing queries
- `src/memory_mcp/repositories/relationships.py` — understand Relationship model
- `src/memory_mcp/models/schema.py` — Entity and Relationship column definitions
- Top 60 lines of `src/memory_mcp/mcp_tools/server.py` — understand imports and helpers

This is required — the MCP tool signatures must match existing model field names exactly.

## Step 2: Write failing tests

```python
# tests/test_entity_graph_tools.py
import pytest
from unittest.mock import patch


def test_upsert_entity_creates_new(mcp_client):
    result = mcp_client.call("upsert_entity", {
        "entity_type": "service",
        "name": "UCX.RequestRouting",
        "aliases": ["request-routing"],
        "attributes": {"language": ".NET"},
        "workspace": "ucx-root",
    })
    assert result["status"] in ("created", "updated")
    assert result["entity"]["name"] == "UCX.RequestRouting"


def test_upsert_entity_is_idempotent(mcp_client):
    args = {"entity_type": "service", "name": "MyService", "workspace": "ws"}
    r1 = mcp_client.call("upsert_entity", args)
    r2 = mcp_client.call("upsert_entity", args)
    assert r1["entity"]["id"] == r2["entity"]["id"]


def test_link_entities(mcp_client):
    e1 = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Producer"})
    e2 = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Consumer"})
    result = mcp_client.call("link_entities", {
        "source_id": e1["entity"]["id"],
        "target_id": e2["entity"]["id"],
        "relationship_type": "produces",
        "description": "Producer emits events consumed by Consumer",
    })
    assert result["status"] in ("created", "updated")


def test_traverse_entity_graph(mcp_client):
    root = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Root"})
    child = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Child"})
    mcp_client.call("link_entities", {
        "source_id": root["entity"]["id"],
        "target_id": child["entity"]["id"],
        "relationship_type": "calls",
    })
    result = mcp_client.call("traverse_entity_graph", {
        "start_entity_id": root["entity"]["id"],
        "max_depth": 1,
    })
    assert result["node_count"] >= 2
    names = [n["name"] for n in result["nodes"]]
    assert "Child" in names


def test_get_related_memories(mcp_client):
    entity = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Svc"})
    result = mcp_client.call("get_related_memories", {
        "entity_id": entity["entity"]["id"],
    })
    assert "memories" in result
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_entity_graph_tools.py -v
```

Expected: ImportError or AttributeError — tools don't exist yet.

## Step 4: Add repository methods

In `src/memory_mcp/repositories/entities.py`, add:

```python
def upsert_entity(
    self,
    entity_type: str,
    name: str,
    aliases: list[str] | None = None,
    attributes: dict | None = None,
    applies_to: dict | None = None,
) -> tuple[Entity, str]:
    """Return (entity, status) where status is 'created' or 'updated'."""
    existing = (
        self.session.query(Entity)
        .filter(Entity.entity_type == entity_type, Entity.name == name)
        .first()
    )
    if existing:
        if aliases is not None:
            existing.aliases = aliases
        if attributes is not None:
            existing.attributes = attributes
        if applies_to is not None:
            existing.applies_to = applies_to
        return existing, "updated"
    entity = Entity(
        entity_type=entity_type,
        name=name,
        aliases=aliases or [],
        attributes=attributes or {},
        applies_to=applies_to or {},
    )
    self.session.add(entity)
    self.session.flush()
    return entity, "created"
```

In `src/memory_mcp/repositories/relationships.py`, add:

```python
def link_entities(
    self,
    source_id: str,
    target_id: str,
    relationship_type: str,
    description: str | None = None,
    evidence: str | None = None,
    applies_to: dict | None = None,
) -> tuple[Relationship, str]:
    existing = (
        self.session.query(Relationship)
        .filter(
            Relationship.source_entity_id == source_id,
            Relationship.target_entity_id == target_id,
            Relationship.relationship_type == relationship_type,
        )
        .first()
    )
    if existing:
        existing.description = description
        return existing, "updated"
    rel = Relationship(
        source_entity_id=source_id,
        target_entity_id=target_id,
        relationship_type=relationship_type,
        description=description,
        evidence=evidence,
        applies_to=applies_to or {},
    )
    self.session.add(rel)
    self.session.flush()
    return rel, "created"

def neighbors(
    self,
    entity_id: str,
    relationship_types: tuple[str, ...] | None = None,
    direction: str = "both",
) -> list[Relationship]:
    """Return direct relationships for an entity."""
    from sqlalchemy import or_
    q = self.session.query(Relationship)
    if direction == "outbound":
        q = q.filter(Relationship.source_entity_id == entity_id)
    elif direction == "inbound":
        q = q.filter(Relationship.target_entity_id == entity_id)
    else:
        q = q.filter(
            or_(
                Relationship.source_entity_id == entity_id,
                Relationship.target_entity_id == entity_id,
            )
        )
    if relationship_types:
        q = q.filter(Relationship.relationship_type.in_(relationship_types))
    return q.all()
```

## Step 5: Add graph traversal to HybridRetrievalService

In `src/memory_mcp/retrieval/service.py`, add:

```python
def traverse_entity_graph(
    self,
    start_entity_id: str,
    relationship_types: tuple[str, ...] | None = None,
    direction: str = "both",
    max_depth: int = 2,
    include_memories: bool = True,
    limit: int = 20,
) -> dict:
    """BFS traversal returning nodes, edges, and attached memories."""
    from memory_mcp.repositories.entities import EntityRepository
    from memory_mcp.repositories.relationships import RelationshipRepository

    entity_repo = EntityRepository(self.session)
    rel_repo = RelationshipRepository(self.session)

    visited_ids: set[str] = set()
    nodes: list[dict] = []
    edges: list[dict] = []
    queue = [(start_entity_id, 0)]

    while queue and len(nodes) < limit:
        eid, depth = queue.pop(0)
        if eid in visited_ids or depth > max_depth:
            continue
        visited_ids.add(eid)
        entity = entity_repo.get_by_id(eid)
        if entity is None:
            continue
        nodes.append({
            "id": str(entity.id),
            "entity_type": entity.entity_type,
            "name": entity.name,
            "aliases": entity.aliases or [],
            "attributes": entity.attributes or {},
        })
        if depth < max_depth:
            rels = rel_repo.neighbors(eid, relationship_types, direction)
            for rel in rels:
                neighbor_id = (
                    str(rel.target_entity_id)
                    if str(rel.source_entity_id) == eid
                    else str(rel.source_entity_id)
                )
                edges.append({
                    "source": str(rel.source_entity_id),
                    "target": str(rel.target_entity_id),
                    "type": rel.relationship_type,
                    "description": rel.description,
                })
                if neighbor_id not in visited_ids:
                    queue.append((neighbor_id, depth + 1))

    memories: list[dict] = []
    if include_memories:
        for node in nodes[:10]:
            ms = self.session.query(Memory).filter(
                Memory.entity_id == node["id"],
                Memory.status == "active",
            ).limit(3).all()
            for m in ms:
                memories.append({"entity_id": node["id"], "memory_id": str(m.id),
                                  "content": m.content})

    return {
        "start_entity_id": start_entity_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "memories": memories,
    }
```

## Step 6: Add MCP tool wrappers in server.py

Add these four tools. Place them after `search_entities` and before `run()`.

```python
@mcp.tool()
def upsert_entity(
    entity_type: str,
    name: str,
    aliases: list[str] | None = None,
    attributes: dict[str, Any] | None = None,
    workspace: str | None = None,
    repo: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Create or update a named entity in the knowledge graph."""
    entity_type = _validate_text("entity_type", entity_type, max_chars=100)
    name = _validate_text("name", name, max_chars=500)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    repo = _validate_text("repo", repo, max_chars=200)
    project = _validate_text("project", project, max_chars=200) or repo
    _authorize_tool_call("upsert_entity", AuthAction.WRITE, workspace=workspace, project=project)
    applies_to: dict[str, Any] = {}
    if workspace:
        applies_to["workspace"] = workspace
    if project:
        applies_to["project"] = project
    with session_scope() as session:
        from memory_mcp.repositories.entities import EntityRepository
        repo_obj = EntityRepository(session)
        entity, status = repo_obj.upsert_entity(
            entity_type=entity_type,
            name=name,
            aliases=aliases,
            attributes=attributes,
            applies_to=applies_to or None,
        )
        session.commit()
        return {
            "status": status,
            "entity": {
                "id": str(entity.id),
                "entity_type": entity.entity_type,
                "name": entity.name,
                "aliases": entity.aliases or [],
                "attributes": entity.attributes or {},
                "applies_to": entity.applies_to or {},
            },
        }


@mcp.tool()
def link_entities(
    source_id: str,
    target_id: str,
    relationship_type: str,
    description: str | None = None,
    evidence: str | None = None,
    workspace: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Create or update a directed relationship between two entities."""
    source_id = _validate_text("source_id", source_id, max_chars=100)
    target_id = _validate_text("target_id", target_id, max_chars=100)
    relationship_type = _validate_text("relationship_type", relationship_type, max_chars=100)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    project = _validate_text("project", project, max_chars=200)
    _authorize_tool_call("link_entities", AuthAction.WRITE, workspace=workspace, project=project)
    applies_to: dict[str, Any] = {}
    if workspace:
        applies_to["workspace"] = workspace
    if project:
        applies_to["project"] = project
    with session_scope() as session:
        from memory_mcp.repositories.relationships import RelationshipRepository
        rel_repo = RelationshipRepository(session)
        rel, status = rel_repo.link_entities(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            description=description,
            evidence=evidence,
            applies_to=applies_to or None,
        )
        session.commit()
        return {
            "status": status,
            "relationship": {
                "source_id": str(rel.source_entity_id),
                "target_id": str(rel.target_entity_id),
                "type": rel.relationship_type,
                "description": rel.description,
            },
        }


@mcp.tool()
def traverse_entity_graph(
    start_entity_id: str,
    relationship_types: list[str] | None = None,
    direction: str = "both",
    max_depth: int = 2,
    include_memories: bool = True,
    limit: int = 20,
) -> dict[str, Any]:
    """BFS traversal of the entity graph from a starting entity."""
    start_entity_id = _validate_text("start_entity_id", start_entity_id, max_chars=100)
    direction = direction if direction in ("outbound", "inbound", "both") else "both"
    max_depth = _bounded_int("max_depth", max_depth, minimum=1, maximum=4)
    limit = _bounded_int("limit", limit, minimum=1, maximum=100)
    _authorize_tool_call("traverse_entity_graph", AuthAction.READ)
    with session_scope() as session:
        retrieval = HybridRetrievalService(session)
        return retrieval.traverse_entity_graph(
            start_entity_id=start_entity_id,
            relationship_types=_tuple_or_none(relationship_types),
            direction=direction,
            max_depth=max_depth,
            include_memories=include_memories,
            limit=limit,
        )


@mcp.tool()
def get_related_memories(
    entity_id: str,
    relationship_types: list[str] | None = None,
    direction: str = "both",
    limit: int = 20,
) -> dict[str, Any]:
    """Return memories attached to an entity and its direct neighbors."""
    entity_id = _validate_text("entity_id", entity_id, max_chars=100)
    direction = direction if direction in ("outbound", "inbound", "both") else "both"
    limit = _bounded_int("limit", limit, minimum=1, maximum=MAX_SEARCH_LIMIT)
    _authorize_tool_call("get_related_memories", AuthAction.READ)
    with session_scope() as session:
        retrieval = HybridRetrievalService(session)
        result = retrieval.traverse_entity_graph(
            start_entity_id=entity_id,
            relationship_types=_tuple_or_none(relationship_types),
            direction=direction,
            max_depth=1,
            include_memories=True,
            limit=limit,
        )
        return {
            "entity_id": entity_id,
            "memories": result["memories"],
            "neighbor_count": result["node_count"] - 1,
        }
```

## Step 7: Syntax check and tests

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_entity_graph_tools.py -v
pytest -v
```

## Step 8: Update ARCHITECTURE.md MCP tool surface table

Add rows:
- `upsert_entity` | Create or update a named entity in the knowledge graph.
- `link_entities` | Create or update a directed relationship between two entities.
- `traverse_entity_graph` | BFS walk from a starting entity, returns nodes, edges, attached memories.
- `get_related_memories` | Return memories attached to an entity and its direct neighbors.

## Merge

```bash
git checkout main
git merge feat/p1-entity-graph --no-ff -m "feat: add P1 entity graph MCP tools (upsert, link, traverse, related)"
git push origin main
```

## Handoff prompt for Track 5

```
Continue memory-mcp roadmap. Track 4 (P1 entity graph tools) is complete and merged to main.
Next: Track 5 — read docs/prompts/impl-p1-code-citations.md and implement it.
Branch off main as feat/p1-code-citations. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 4 status from ⬜ to ✅ before starting Track 5.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-p1-entity-graph.md
git commit -m "docs(prompts): add Track 4 P1 entity graph tools prompt"
```

---

## Task 7: Create impl-p1-code-citations.md

**Files:**
- Create: `docs/prompts/impl-p1-code-citations.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — P1 Code Citations + QW3 cited_path Filter

**Model:** Sonnet
**Estimated effort:** 4–6 hrs
**Branch:** `feat/p1-code-citations`

## Context

Adds a `code_citations` JSONB column to `memories` so a memory can cite specific
files, symbols, or endpoints in the codebase. Also adds a `cited_path` filter to
`search_memory` (QW3 — previously deferred until this column existed).

## Relevant files

- Create: `migrations/versions/0007_code_citations.py`
- Modify: `src/memory_mcp/models/schema.py` — add `code_citations` column
- Modify: `src/memory_mcp/mcp_tools/server.py` — validator + tool params + cited_path filter
- Test: `tests/test_code_citations.py` (new)

## Citation schema

Each citation is a dict:
```json
{
  "repo": "UCX.RequestRouting",
  "path": "Application/Services/Implementation/RoutingService.cs",
  "lines": [42, 87],
  "symbol": "RoutingService.GetNextReviewer",
  "commit": "abc1234",
  "kind": "symbol"
}
```

Valid `kind` values: `"file"`, `"symbol"`, `"event"`, `"endpoint"`.
Max 20 citations per memory. Path must be relative (no leading `/` or drive letter).

## Step 1: Write failing tests

```python
# tests/test_code_citations.py
import pytest


def test_add_memory_with_citations(mcp_client):
    result = mcp_client.call("add_memory", {
        "content": "RoutingService determines reviewer by specialty.",
        "memory_type": "project_fact",
        "memory_scope": "project",
        "project": "UCX.RequestRouting",
        "code_citations": [
            {"repo": "UCX.RequestRouting",
             "path": "Application/Services/RoutingService.cs",
             "kind": "file"}
        ],
    })
    assert result["status"] == "created"


def test_citations_rejected_when_too_many(mcp_client):
    with pytest.raises(Exception, match="code_citations"):
        mcp_client.call("add_memory", {
            "content": "Test.",
            "memory_type": "project_fact",
            "memory_scope": "project",
            "code_citations": [{"repo": "r", "path": f"file{i}.py", "kind": "file"}
                                for i in range(21)],
        })


def test_citations_rejected_for_absolute_path(mcp_client):
    with pytest.raises(Exception, match="absolute"):
        mcp_client.call("add_memory", {
            "content": "Test.",
            "memory_type": "project_fact",
            "memory_scope": "project",
            "code_citations": [{"repo": "r", "path": "/etc/passwd", "kind": "file"}],
        })


def test_search_memory_cited_path_filter(mcp_client):
    mcp_client.call("add_memory", {
        "content": "Routing logic lives here.",
        "memory_type": "project_fact",
        "memory_scope": "project",
        "project": "UCX.RequestRouting",
        "code_citations": [{"repo": "UCX.RequestRouting",
                             "path": "Application/Services/RoutingService.cs",
                             "kind": "file"}],
    })
    result = mcp_client.call("search_memory", {
        "query": "routing",
        "cited_path": "Application/Services/RoutingService.cs",
    })
    assert result["count"] >= 1
```

## Step 2: Write migration

```python
# migrations/versions/0007_code_citations.py
"""Add code_citations JSONB column to memories.

Revision ID: 0007_code_citations
Revises: 0006_embedding_hnsw_index
Create Date: 2026-05-11
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007_code_citations"
down_revision = "0006_embedding_hnsw_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "memories",
        sa.Column("code_citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_memories_code_citations_gin",
        "memories",
        ["code_citations"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_memories_code_citations_gin", table_name="memories")
    op.drop_column("memories", "code_citations")
```

## Step 3: Add column to Memory model

In `src/memory_mcp/models/schema.py`, add to the `Memory` class:

```python
code_citations = Column(JSONB, nullable=True)
```

## Step 4: Add validator to server.py

After `_check_content_for_secrets`, add:

```python
_MAX_CITATIONS = 20
_VALID_CITATION_KINDS = frozenset({"file", "symbol", "event", "endpoint"})


def _validate_code_citations(citations: Any) -> list[dict] | None:
    if citations is None:
        return None
    if not isinstance(citations, list):
        raise ValueError("code_citations must be a list")
    if len(citations) > _MAX_CITATIONS:
        raise ValueError(f"code_citations must not exceed {_MAX_CITATIONS} items")
    result = []
    for c in citations:
        if not isinstance(c, dict):
            raise ValueError("each code_citation must be a dict")
        path = c.get("path", "")
        if not path:
            raise ValueError("code_citation must have a path")
        if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
            raise ValueError(f"code_citation path must be relative, got: {path!r} (absolute paths disallowed)")
        if len(path) > 500:
            raise ValueError("code_citation path too long (max 500 chars)")
        kind = c.get("kind", "file")
        if kind not in _VALID_CITATION_KINDS:
            raise ValueError(f"code_citation kind must be one of {sorted(_VALID_CITATION_KINDS)}")
        result.append({k: v for k, v in c.items()})
    return result
```

## Step 5: Add `code_citations` parameter to add_memory and supersede_memory

In `add_memory` and `supersede_memory`, after `_check_content_for_secrets(content)`:

```python
code_citations = _validate_code_citations(code_citations)
```

Pass `code_citations=code_citations` to the `MemoryService` call.

In `MemoryService.add_memory` (or wherever the Memory ORM object is created), set:

```python
memory.code_citations = code_citations
```

## Step 6: Add `cited_path` filter to search_memory

In the `search_memory` MCP tool, add parameter `cited_path: str | None = None`.

In the retrieval call, if `cited_path` is provided, add a JSONB containment filter:

```python
# In HybridRetrievalService.search_memories or the query building:
if cited_path:
    from sqlalchemy import cast, func
    q = q.filter(
        Memory.code_citations.op("@>")(
            cast(f'[{{"path": "{cited_path}"}}]', JSONB)
        )
    )
```

Or use a path prefix match with `func.jsonb_path_exists`:
```python
q = q.filter(
    func.jsonb_path_exists(
        Memory.code_citations,
        f'$[*] ? (@.path starts with "{cited_path}")',
    )
)
```

## Step 7: Run migration and tests

```bash
alembic upgrade head
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_code_citations.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p1-code-citations --no-ff -m "feat: add P1 code citations column and QW3 cited_path filter"
git push origin main
```

## Handoff prompt for Track 6

```
Continue memory-mcp roadmap. Track 5 (P1 code citations + QW3) is complete and merged to main.
Next: Track 6 — read docs/prompts/impl-p1-classifier.md and implement it.
Branch off main as feat/p1-classifier. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 5 status from ⬜ to ✅ before starting Track 6.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-p1-code-citations.md
git commit -m "docs(prompts): add Track 5 P1 code citations prompt"
```

---

## Task 8: Create impl-p1-classifier.md

**Files:**
- Create: `docs/prompts/impl-p1-classifier.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — P1 Classifier Upgrade (Two-Pass Entity Matching)

**Model:** Sonnet
**Estimated effort:** 4–6 hrs
**Branch:** `feat/p1-classifier`

## Context

`ContextSynthesisService` uses a lexical keyword classifier to determine request
domain. This track upgrades it to a two-pass classifier that also extracts matched
entities from the entity graph, exposing them in `RequestClassification` so that
retrieval can use entity-id hints and entity names for better precision.

Track 4 (entity graph tools) must be merged before this track starts.

## Relevant files

- Modify: `src/memory_mcp/services/context_synthesis.py` — extend classifier
- Modify: `src/memory_mcp/retrieval/service.py` — accept entity hints
- Test: `tests/test_context_synthesis.py` — extend existing tests

## Step 1: Read existing classifier

Read `src/memory_mcp/services/context_synthesis.py` in full. Understand:
- `RequestClassification` dataclass fields
- How `_classify_request` works (lexical matching)
- How `ContextSynthesisService.synthesize` uses the classification

## Step 2: Write failing tests

```python
# tests/test_context_synthesis.py — add to existing test file

def test_classification_exposes_matched_entities(synthesis_service, seeded_entities):
    """After entity graph is seeded, classifier should find entity matches."""
    classification = synthesis_service.classify_request(
        "Why is UCX.RequestRouting not routing cases correctly?"
    )
    assert hasattr(classification, "matched_entities")
    assert hasattr(classification, "hinted_repos")
    # May be empty if entity search returns nothing — just assert field exists

def test_classification_matched_entities_is_list(synthesis_service):
    classification = synthesis_service.classify_request("general question")
    assert isinstance(classification.matched_entities, list)
    assert isinstance(classification.hinted_repos, list)
    assert isinstance(classification.hinted_memory_types, list)
```

## Step 3: Extend RequestClassification

In `context_synthesis.py`, extend the `RequestClassification` dataclass:

```python
@dataclass
class RequestClassification:
    domain: str
    confidence: float
    matched_terms: list[str]
    # New fields:
    matched_entities: list[dict]   # [{"id": ..., "name": ..., "entity_type": ...}]
    hinted_memory_types: list[str] # e.g. ["architecture_decision", "project_fact"]
    hinted_repos: list[str]        # repo names extracted from the request
```

Update all construction sites to include the new fields (default to empty lists for backward compat).

## Step 4: Add entity-matching pass to classifier

In `ContextSynthesisService`, add a private method:

```python
def _match_entities_in_request(self, request: str, session) -> list[dict]:
    """Run search_entities against the request text, return top hits."""
    try:
        from memory_mcp.retrieval.service import HybridRetrievalService
        retrieval = HybridRetrievalService(session)
        results = retrieval.search_entities(
            text_query=request,
            limit=5,
        )
        return [
            {"id": str(r.entity.id), "name": r.entity.name,
             "entity_type": r.entity.entity_type}
            for r in results
            if r.rank_score is None or r.rank_score > 0.3
        ]
    except Exception:
        return []
```

In `classify_request` (or wherever it's called with a session), call this method
and populate `matched_entities`. Extract `hinted_repos` by looking for entity hits
where `entity_type == "service"` or `entity_type == "repo"`.

## Step 5: Pass entity hints to retrieval

In `synthesize()`, after classification, if `matched_entities` is non-empty,
pass entity IDs as hints to `search_memories`:

```python
entity_id_hints = [e["id"] for e in classification.matched_entities]
# Pass to retrieval — if HybridRetrievalService.search_memories accepts entity_ids,
# use them as a filter boost or pre-filter. If not, add that parameter now.
```

In `HybridRetrievalService.search_memories`, add `entity_id_hints: list[str] | None = None`.
When provided, boost results whose `memory.entity_id` is in the hint list by adding
0.1 to their rank score.

## Step 6: Run tests

```bash
pytest tests/test_context_synthesis.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p1-classifier --no-ff -m "feat: add P1 two-pass entity-matching classifier upgrade"
git push origin main
```

## Handoff prompt for Track 7

```
Continue memory-mcp roadmap. Track 6 (P1 classifier) is complete and merged to main.
Next: Track 7 — read docs/prompts/impl-p2-event-flow.md and implement it.
Branch off main as feat/p2-event-flow. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 6 status from ⬜ to ✅ before starting Track 7.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-p1-classifier.md
git commit -m "docs(prompts): add Track 6 P1 classifier upgrade prompt"
```

---

## Task 9: Create impl-p2-event-flow.md

**Files:**
- Create: `docs/prompts/impl-p2-event-flow.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — P2 Event-Flow Memory Types + get_event_flow Tool

**Model:** Sonnet
**Estimated effort:** 3–5 hrs
**Branch:** `feat/p2-event-flow`

## Context

Adds two new memory types (`event_contract`, `service_dependency`) and a new MCP
tool `get_event_flow(event_name)` for event-sourced programs like ucx-root.
This is convention-based (stored in JSONB metadata), not a schema change.

## Relevant files

- Modify: `src/memory_mcp/models/types.py` — add new memory types to the enum/list
- Modify: `src/memory_mcp/mcp_tools/server.py` — add `get_event_flow` tool
- Modify: `src/memory_mcp/services/context_synthesis.py` — include event flow in packet when request references an event
- Test: `tests/test_event_flow.py` (new)

## Canonical metadata shape for event_contract

```json
{
  "event_name": "UserProfileConfigurationUpdated",
  "producers": [{"service": "UCX.ConfigurationService", "file": "..."}],
  "consumers": [{"service": "Ucx.RequestRouting", "handler": "..."}],
  "schema_repo": "ucx.messages",
  "schema_symbol": "UserProfileConfigurationUpdatedEvent"
}
```

## Step 1: Read types.py

Read `src/memory_mcp/models/types.py`. Understand how memory types are defined.
Add `"event_contract"` and `"service_dependency"` to the valid set.
This may be a list, a TypedDict, or an Enum — match the existing pattern exactly.

## Step 2: Write failing tests

```python
# tests/test_event_flow.py

def test_add_event_contract_memory(mcp_client):
    result = mcp_client.call("add_memory", {
        "content": "UserProfileConfigurationUpdated is produced by UCX.ConfigurationService.",
        "memory_type": "event_contract",
        "memory_scope": "workspace",
        "workspace": "ucx-root",
        "tags": ["event:UserProfileConfigurationUpdated"],
        "metadata": {
            "event_name": "UserProfileConfigurationUpdated",
            "producers": [{"service": "UCX.ConfigurationService"}],
            "consumers": [{"service": "Ucx.RequestRouting"}],
            "schema_repo": "ucx.messages",
        },
    })
    assert result["status"] == "created"


def test_get_event_flow_returns_producers_and_consumers(mcp_client):
    mcp_client.call("add_memory", {
        "content": "OrderCreated is produced by OrderService.",
        "memory_type": "event_contract",
        "memory_scope": "workspace",
        "workspace": "test-ws",
        "metadata": {
            "event_name": "OrderCreated",
            "producers": [{"service": "OrderService"}],
            "consumers": [{"service": "InventoryService"}],
        },
    })
    result = mcp_client.call("get_event_flow", {"event_name": "OrderCreated", "workspace": "test-ws"})
    assert result["event_name"] == "OrderCreated"
    assert len(result["producers"]) >= 1
    assert len(result["consumers"]) >= 1


def test_get_event_flow_empty_when_not_found(mcp_client):
    result = mcp_client.call("get_event_flow", {"event_name": "NonExistentEvent"})
    assert result["count"] == 0
```

## Step 3: Add get_event_flow MCP tool

In `server.py`, before `run()`:

```python
@mcp.tool()
def get_event_flow(
    event_name: str,
    workspace: str | None = None,
    repo: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Return producers, consumers, and handlers for a named event."""
    event_name = _validate_text("event_name", event_name, max_chars=500)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    repo = _validate_text("repo", repo, max_chars=200)
    project = _validate_text("project", project, max_chars=200) or repo
    _authorize_tool_call("get_event_flow", AuthAction.READ, workspace=workspace, project=project)

    with session_scope() as session:
        from sqlalchemy import cast, func
        from memory_mcp.models.schema import Memory
        from sqlalchemy.dialects.postgresql import JSONB

        q = (
            session.query(Memory)
            .filter(
                Memory.memory_type == "event_contract",
                Memory.status == "active",
                func.jsonb_path_exists(
                    Memory.metadata_,
                    f'$ ? (@.event_name == "{event_name}")',
                ),
            )
        )
        if workspace:
            q = q.filter(Memory.applies_to["workspace"].astext == workspace)

        memories = q.limit(20).all()
        producers: list[dict] = []
        consumers: list[dict] = []
        schema_info: dict = {}
        for m in memories:
            meta = m.metadata_ or {}
            producers.extend(meta.get("producers", []))
            consumers.extend(meta.get("consumers", []))
            if not schema_info:
                schema_info = {k: meta[k] for k in ("schema_repo", "schema_symbol") if k in meta}

        return {
            "event_name": event_name,
            "count": len(memories),
            "producers": producers,
            "consumers": consumers,
            "schema": schema_info,
            "memory_ids": [str(m.id) for m in memories],
        }
```

## Step 4: Context synthesis — include event flow in packet

In `context_synthesis.py`, in the `synthesize` method, after building the main
facts list: scan the request for known event names (search memories with
`memory_type=event_contract` where `metadata_.event_name` appears in the request
text). If any match, append a summary to `packet.facts`.

This is a lightweight scan — avoid N+1; do a single query with `ILIKE` on `content`:

```python
# Detect event names in request
event_memories = session.query(Memory).filter(
    Memory.memory_type == "event_contract",
    Memory.status == "active",
    Memory.content.ilike(f"%{request[:100]}%"),
).limit(3).all()
for em in event_memories:
    meta = em.metadata_ or {}
    if meta.get("event_name"):
        packet_facts.append(
            f"Event {meta['event_name']}: "
            f"produced by {meta.get('producers', [])}, "
            f"consumed by {meta.get('consumers', [])}"
        )
```

## Step 5: Run tests

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_event_flow.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p2-event-flow --no-ff -m "feat: add P2 event-flow memory types and get_event_flow tool"
git push origin main
```

## Handoff prompt for Track 8

```
Continue memory-mcp roadmap. Track 7 (P2 event-flow) is complete and merged to main.
Next: Track 8 — read docs/prompts/impl-p2-packet-diagnostics.md and implement it.
Branch off main as feat/p2-packet-diagnostics. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 7 status from ⬜ to ✅ before starting Track 8.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-p2-event-flow.md
git commit -m "docs(prompts): add Track 7 P2 event-flow prompt"
```

---

## Task 10: Create impl-p2-packet-diagnostics.md

**Files:**
- Create: `docs/prompts/impl-p2-packet-diagnostics.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — P2 Context Packet Quality Signals (Multi-Repo Diagnostics)

**Model:** Sonnet
**Estimated effort:** 3–4 hrs
**Branch:** `feat/p2-packet-diagnostics`

## Context

`get_context_packet` returns a `context_quality` signal and `suggested_next_action`.
This track extends diagnostics with per-dimension signals useful for multi-repo
workspaces: which repos matched, which entities matched, which event names matched,
and per-layer memory counts. `suggested_next_action` also gets smarter branching.

## Relevant files

- Modify: `src/memory_mcp/services/context_synthesis.py` — extend diagnostics
- Modify: `src/memory_mcp/mcp_tools/server.py` — expose new fields in response
- Test: `tests/test_context_synthesis.py` — extend

## Step 1: Read context_synthesis.py

Read the full file. Understand `ContextPacket` and `diagnostics` dict shape.
Note what fields currently exist in the diagnostics output.

## Step 2: Write failing tests

```python
# tests/test_context_synthesis.py — add:

def test_diagnostics_include_matched_repos(synthesis_service, seeded_memories):
    packet = synthesis_service.synthesize(
        request="How does UCX.RequestRouting work?",
        workspace="ucx-root",
    )
    assert "matched_repos" in packet.diagnostics
    assert isinstance(packet.diagnostics["matched_repos"], list)


def test_diagnostics_include_per_layer_counts(synthesis_service, seeded_memories):
    packet = synthesis_service.synthesize(request="test", workspace="ucx-root")
    assert "per_layer_counts" in packet.diagnostics
    counts = packet.diagnostics["per_layer_counts"]
    assert "workspace" in counts or "project" in counts


def test_suggested_next_action_get_event_flow_when_event_missing(synthesis_service):
    packet = synthesis_service.synthesize(
        request="What produces UserProfileConfigurationUpdated?",
        workspace="ucx-root",
    )
    # If no event_contract memories exist, suggest get_event_flow
    if packet.context_quality == "weak":
        assert "get_event_flow" in packet.suggested_next_action or \
               "traverse_entity_graph" in packet.suggested_next_action or \
               "mark_weak_context" in packet.suggested_next_action
```

## Step 3: Extend diagnostics in ContextPacket / synthesize

In `context_synthesis.py`, after building the memory result list, collect:

```python
# matched_repos: unique applies_to["repo"] values from matched memories
matched_repos = list({
    m.memory.applies_to.get("repo")
    for m in results
    if m.memory.applies_to and m.memory.applies_to.get("repo")
})

# matched_entities: unique entity names from matched memories
matched_entities = list({
    m.memory.entity_id for m in results if m.memory.entity_id
})

# matched_event_names: from event_contract memories in results
matched_event_names = [
    m.memory.metadata_.get("event_name")
    for m in results
    if m.memory.memory_type == "event_contract" and m.memory.metadata_
]

# per_layer_counts: count by memory_scope
from collections import Counter
per_layer_counts = dict(Counter(m.memory.memory_scope for m in results))
```

Add these to `diagnostics`:
```python
diagnostics.update({
    "matched_repos": matched_repos,
    "matched_entities": matched_entities,
    "matched_event_names": matched_event_names,
    "per_layer_counts": per_layer_counts,
})
```

## Step 4: Upgrade suggested_next_action branching

Replace or extend the current simple suggestion logic:

```python
def _suggest_next_action(packet, classification) -> str:
    if packet.context_quality == "strong":
        return "answer_from_packet"
    diag = packet.diagnostics
    if not diag.get("matched_repos") and classification.hinted_repos:
        return (f"run get_context_packet with repo={classification.hinted_repos[0]!r} "
                f"to narrow scope, or run search_memory with that repo filter")
    if classification.matched_entities and not diag.get("matched_event_names"):
        event_hint = next(
            (e["name"] for e in classification.matched_entities
             if "event" in e.get("entity_type", "").lower()), None
        )
        if event_hint:
            return f"run get_event_flow(event_name={event_hint!r}) for event producer/consumer context"
    if not diag.get("matched_entities") and classification.matched_entities:
        eid = classification.matched_entities[0]["id"]
        return f"run traverse_entity_graph(start_entity_id={eid!r}) for graph context"
    if packet.context_quality == "weak":
        return "mark_weak_context — no strong matches; consider adding memories for this project"
    return "verify_narrowly"
```

## Step 5: Run tests

```bash
pytest tests/test_context_synthesis.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p2-packet-diagnostics --no-ff -m "feat: add P2 multi-repo context packet diagnostics"
git push origin main
```

## Handoff prompt for Track 9

```
Continue memory-mcp roadmap. Track 8 (P2 packet diagnostics) is complete and merged to main.
Next: Track 9 — read docs/prompts/impl-p2-code-graph-import.md and implement it.
Branch off main as feat/p2-code-graph-import. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 8 status from ⬜ to ✅ before starting Track 9.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-p2-packet-diagnostics.md
git commit -m "docs(prompts): add Track 8 P2 packet diagnostics prompt"
```

---

## Task 11: Create impl-p2-code-graph-import.md

**Files:**
- Create: `docs/prompts/impl-p2-code-graph-import.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — P2 Import Code Graph Summary Tool

**Model:** Sonnet
**Estimated effort:** 3–4 hrs
**Branch:** `feat/p2-code-graph-import`

## Context

Adds `import_code_graph_summary` MCP tool: accepts a bounded, schema-validated
JSON payload from an external code graph tool and writes the content as
`project_fact` or `architecture_decision` memories with code citations.
This is glue — memory-mcp does not parse code itself.

## Relevant files

- Modify: `src/memory_mcp/mcp_tools/server.py` — add tool
- Test: `tests/test_code_graph_import.py` (new)

## Accepted payload schema (versioned)

```json
{
  "schema_version": "1",
  "repo": "UCX.RequestRouting",
  "workspace": "ucx-root",
  "summaries": [
    {
      "memory_type": "architecture_decision",
      "content": "RoutingService decides reviewer by specialty and state license.",
      "scope": "component",
      "component": "routing",
      "code_citations": [
        {"repo": "UCX.RequestRouting",
         "path": "Application/Services/RoutingService.cs",
         "kind": "symbol",
         "symbol": "RoutingService.GetNextReviewer"}
      ],
      "tags": ["routing", "reviewer-selection"]
    }
  ]
}
```

Constraints:
- `schema_version` must be `"1"`
- `summaries` max 50 items
- Each `content` max 4000 chars
- Each item must have `memory_type` in the valid set
- Unknown keys at the top level are rejected
- Unknown keys inside summaries are ignored (forward compat)

## Step 1: Write failing tests

```python
# tests/test_code_graph_import.py

VALID_PAYLOAD = {
    "schema_version": "1",
    "repo": "UCX.RequestRouting",
    "workspace": "ucx-root",
    "summaries": [
        {
            "memory_type": "architecture_decision",
            "content": "RoutingService decides reviewer by specialty.",
            "scope": "component",
            "component": "routing",
            "code_citations": [
                {"repo": "UCX.RequestRouting",
                 "path": "Application/Services/RoutingService.cs",
                 "kind": "symbol"}
            ],
        }
    ],
}


def test_import_creates_memories(mcp_client):
    result = mcp_client.call("import_code_graph_summary", {"payload": VALID_PAYLOAD})
    assert result["created"] >= 1
    assert result["errors"] == []


def test_import_is_idempotent(mcp_client):
    r1 = mcp_client.call("import_code_graph_summary", {"payload": VALID_PAYLOAD})
    r2 = mcp_client.call("import_code_graph_summary", {"payload": VALID_PAYLOAD})
    assert r1["created"] >= 1
    assert r2["created"] == 0  # second run: all superseded or unchanged


def test_import_rejects_wrong_schema_version(mcp_client):
    bad = {**VALID_PAYLOAD, "schema_version": "99"}
    with pytest.raises(Exception, match="schema_version"):
        mcp_client.call("import_code_graph_summary", {"payload": bad})


def test_import_rejects_too_many_summaries(mcp_client):
    big = {**VALID_PAYLOAD, "summaries": [VALID_PAYLOAD["summaries"][0]] * 51}
    with pytest.raises(Exception, match="summaries"):
        mcp_client.call("import_code_graph_summary", {"payload": big})
```

## Step 2: Add tool to server.py

```python
_ALLOWED_IMPORT_TOP_KEYS = frozenset({"schema_version", "repo", "workspace", "summaries"})


@mcp.tool()
def import_code_graph_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept a code-graph summary payload and write it as typed memories."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    unknown = set(payload.keys()) - _ALLOWED_IMPORT_TOP_KEYS
    if unknown:
        raise ValueError(f"Unknown top-level keys: {sorted(unknown)}")
    if payload.get("schema_version") != "1":
        raise ValueError("schema_version must be '1'")
    summaries = payload.get("summaries", [])
    if not isinstance(summaries, list):
        raise ValueError("summaries must be a list")
    if len(summaries) > 50:
        raise ValueError("summaries must not exceed 50 items")

    repo = _validate_text("repo", payload.get("repo"), max_chars=200)
    workspace = _validate_text("workspace", payload.get("workspace"), max_chars=200)
    _authorize_tool_call("import_code_graph_summary", AuthAction.WRITE,
                         workspace=workspace, project=repo)

    created = updated = skipped = 0
    errors: list[str] = []

    with session_scope() as session:
        from memory_mcp.ingest.writer import IngestWriter
        writer = IngestWriter(session)
        for i, summary in enumerate(summaries):
            try:
                content = summary.get("content", "")
                if len(content) > 4000:
                    raise ValueError("content exceeds 4000 chars")
                memory_type = summary.get("memory_type", "project_fact")
                citations = _validate_code_citations(summary.get("code_citations"))
                ingest_key = f"cgraph:{workspace}:{repo}:{i}:{hash(content)}"
                applies_to: dict[str, Any] = {}
                if workspace:
                    applies_to["workspace"] = workspace
                if repo:
                    applies_to[REPO_KEY] = repo
                    applies_to["project"] = repo
                if summary.get("component"):
                    applies_to["component"] = summary["component"]

                result = writer.upsert(
                    content=content,
                    memory_type=memory_type,
                    memory_scope=summary.get("scope", "project"),
                    applies_to=applies_to,
                    tags=summary.get("tags", []) + ["ingest:code-graph"],
                    metadata={"ingest_key": ingest_key},
                    code_citations=citations,
                )
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors.append(f"summary[{i}]: {exc}")

        session.commit()

    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}
```

## Step 3: Run tests

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_code_graph_import.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p2-code-graph-import --no-ff -m "feat: add P2 import_code_graph_summary MCP tool"
git push origin main
```

## Handoff prompt for Track 10

```
Continue memory-mcp roadmap. Track 9 (P2 code graph import) is complete and merged to main.
Next: Track 10 — read docs/prompts/impl-p2-benchmarks.md and implement it.
Branch off main as feat/p2-benchmarks. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 9 status from ⬜ to ✅ before starting Track 10.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-p2-code-graph-import.md
git commit -m "docs(prompts): add Track 9 P2 code graph import prompt"
```

---

## Task 12: Create impl-p2-benchmarks.md

**Files:**
- Create: `docs/prompts/impl-p2-benchmarks.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — P2 Multi-Repo Benchmark Harness

**Model:** Sonnet
**Estimated effort:** 1 day
**Branch:** `feat/p2-benchmarks`

## Context

Adds a multi-repo benchmark harness to validate retrieval precision and recall
against a synthetic corpus that mimics a nine-service workspace. This should run
after Tracks 2, 4, 5, 6 are merged (semantic retrieval, entity graph, code
citations, classifier).

## Relevant files

- Create: `benchmarks/multi_repo_cases.json` — 40+ benchmark cases
- Create: `benchmarks/run_multi_repo_benchmarks.py` — runner script
- Create: `benchmarks/corpus/seed_multi_repo_corpus.py` — corpus seeder
- Create: `benchmarks/results/` — results directory (already exists)
- Test: `tests/test_multi_repo_benchmarks.py` (smoke test only)

## Synthetic corpus shape

The corpus mimics ucx-root without real content. Seed these memory shapes:

```python
CORPUS = [
    # Workspace-level
    {"content": "UCX workspace contains 9 .NET microservices and 2 React SPAs.",
     "memory_type": "project_fact", "memory_scope": "workspace",
     "applies_to": {"workspace": "ucx-root"}},
    # Repo-level facts
    {"content": "UCX.RequestRouting decides reviewer by specialty and state license.",
     "memory_type": "architecture_decision", "memory_scope": "project",
     "applies_to": {"workspace": "ucx-root", "repo": "UCX.RequestRouting", "project": "UCX.RequestRouting"}},
    {"content": "Ucx.CaseDetails stores case state in CosmosDB.",
     "memory_type": "project_fact", "memory_scope": "project",
     "applies_to": {"workspace": "ucx-root", "repo": "Ucx.CaseDetails", "project": "Ucx.CaseDetails"}},
    # Event contracts
    {"content": "UserProfileConfigurationUpdated is produced by UCX.ConfigurationService and consumed by Ucx.RequestRouting.",
     "memory_type": "event_contract", "memory_scope": "workspace",
     "applies_to": {"workspace": "ucx-root"},
     "metadata": {"event_name": "UserProfileConfigurationUpdated",
                  "producers": [{"service": "UCX.ConfigurationService"}],
                  "consumers": [{"service": "Ucx.RequestRouting"}]}},
    # Component facts
    {"content": "UCX.UI has 24 feature folders organized by domain.",
     "memory_type": "project_fact", "memory_scope": "component",
     "applies_to": {"workspace": "ucx-root", "repo": "UCX.UI", "component": "ui"}},
    # ... add 35+ more covering all 9 services, key events, ADRs, coding prefs
]
```

## Benchmark cases format

```json
[
  {
    "id": "mr-001",
    "query": "How does request routing decide which reviewer to assign?",
    "workspace": "ucx-root",
    "repo": "UCX.RequestRouting",
    "gold_content_keywords": ["reviewer", "specialty", "state license"],
    "expected_memory_types": ["architecture_decision"],
    "min_precision_at_8": 0.7
  },
  {
    "id": "mr-002",
    "query": "What services consume UserProfileConfigurationUpdated?",
    "workspace": "ucx-root",
    "gold_content_keywords": ["UserProfileConfigurationUpdated", "Ucx.RequestRouting"],
    "expected_memory_types": ["event_contract"],
    "min_precision_at_8": 0.7
  }
]
```

Write at least 40 cases covering: workspace facts, per-repo architecture decisions,
event contracts, component facts, coding preferences, cross-service relationships.

## Runner script

```python
#!/usr/bin/env python
"""Run multi-repo benchmark cases against a live memory-mcp DB.

Usage:
  python benchmarks/run_multi_repo_benchmarks.py --seed --report
"""
import argparse
import json
import datetime
from pathlib import Path
from memory_mcp.db import session_scope
from memory_mcp.retrieval.service import HybridRetrievalService


def precision_at_k(results, gold_keywords, k=8):
    top_k = results[:k]
    hits = sum(
        1 for r in top_k
        if any(kw.lower() in r.memory.content.lower() for kw in gold_keywords)
    )
    return hits / min(k, len(top_k)) if top_k else 0.0


def run_case(case: dict) -> dict:
    with session_scope() as session:
        retrieval = HybridRetrievalService(session)
        applies_to = {"workspace": case["workspace"]}
        if case.get("repo"):
            applies_to["repo"] = case["repo"]
        results = retrieval.search_memories(
            text_query=case["query"],
            applies_to=applies_to,
            limit=8,
        )
        prec = precision_at_k(results, case["gold_content_keywords"])
        return {
            "id": case["id"],
            "query": case["query"],
            "precision_at_8": prec,
            "pass": prec >= case.get("min_precision_at_8", 0.7),
            "result_count": len(results),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true", help="Seed corpus before running")
    parser.add_argument("--report", action="store_true", help="Write results JSON")
    args = parser.parse_args()

    if args.seed:
        from benchmarks.corpus.seed_multi_repo_corpus import seed
        seed()

    cases = json.loads(Path("benchmarks/multi_repo_cases.json").read_text())
    results = [run_case(c) for c in cases]

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    avg_prec = sum(r["precision_at_8"] for r in results) / total if total else 0

    print(f"\nResults: {passed}/{total} passed | avg precision@8: {avg_prec:.2f}")
    for r in results:
        status = "✅" if r["pass"] else "❌"
        print(f"  {status} {r['id']} precision={r['precision_at_8']:.2f} ({r['result_count']} results)")

    if avg_prec < 0.7:
        print("\nWARNING: average precision@8 below 0.7 threshold")

    if args.report:
        out = Path("benchmarks/results") / f"multi-repo-{datetime.date.today()}.json"
        out.write_text(json.dumps({"date": str(datetime.date.today()),
                                   "avg_precision_at_8": avg_prec,
                                   "passed": passed, "total": total,
                                   "cases": results}, indent=2))
        print(f"Report written to {out}")


if __name__ == "__main__":
    main()
```

## Smoke test

```python
# tests/test_multi_repo_benchmarks.py
import json
from pathlib import Path

def test_benchmark_cases_file_exists_and_has_40_cases():
    cases = json.loads(Path("benchmarks/multi_repo_cases.json").read_text())
    assert len(cases) >= 40

def test_each_case_has_required_fields():
    cases = json.loads(Path("benchmarks/multi_repo_cases.json").read_text())
    for case in cases:
        assert "id" in case
        assert "query" in case
        assert "gold_content_keywords" in case
        assert isinstance(case["gold_content_keywords"], list)
        assert len(case["gold_content_keywords"]) >= 1
```

## Run

```bash
pytest tests/test_multi_repo_benchmarks.py -v
python benchmarks/run_multi_repo_benchmarks.py --seed --report
```

## Merge

```bash
git checkout main
git merge feat/p2-benchmarks --no-ff -m "feat: add P2 multi-repo benchmark harness"
git push origin main
```

## Handoff prompt for Track 11

```
Continue memory-mcp roadmap. Track 10 (P2 benchmarks) is complete and merged to main.
Next: Track 11 — read docs/prompts/impl-p3-hook-pack.md and implement it.
Branch off main as feat/p3-hook-pack. Use Haiku.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 10 status from ⬜ to ✅ before starting Track 11.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-p2-benchmarks.md
git commit -m "docs(prompts): add Track 10 P2 multi-repo benchmark harness prompt"
```

---

## Task 13: Create impl-p3-hook-pack.md

**Files:**
- Create: `docs/prompts/impl-p3-hook-pack.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — P3 Client Hook Pack (UCX-Style Workspace)

**Model:** Haiku
**Estimated effort:** 2–4 hrs
**Branch:** `feat/p3-hook-pack`

## Context

Adds a reference client hook pack for UCX-style multi-repo workspaces.
This is documentation and templates only — no application code changes.
The pack lives in `client-setups/ucx-workspace/` and is clearly labeled
"reference, not required."

## Files to create

- `client-setups/ucx-workspace/README.md`
- `client-setups/ucx-workspace/ingest.manifest.yaml`
- `client-setups/ucx-workspace/AGENTS.md`
- `client-setups/ucx-workspace/hooks/pre-session-check.py`

## Step 1: Create README.md

```markdown
# UCX-Style Workspace Hook Pack

Reference configuration for a multi-repo workspace using memory-mcp.
**This is optional** — copy what you need, ignore the rest.

## Contents

| File | Purpose |
|------|---------|
| `ingest.manifest.yaml` | Manifest template for `scripts/ingest_workspace.py` |
| `AGENTS.md` | Memory-first agent workflow description |
| `hooks/pre-session-check.py` | Pre-session hook that warns when the store is empty |

## Setup

1. Copy this folder into your workspace root (e.g. `ucx-root/.memory-mcp/`).
2. Edit `ingest.manifest.yaml` with your workspace name and repo list.
3. Run: `python scripts/ingest_markdown_workspace.py --workspace <name> --dir <root>`
4. Install the pre-session hook in your client (see `client-setups/claude-code/`).
```

## Step 2: Create ingest.manifest.yaml

```yaml
# ingest.manifest.yaml — populate for your workspace
workspace: ucx-root  # change to your workspace name

sources:
  # Markdown docs ingested as project_fact / architecture_decision memories
  markdown:
    - glob: "ucx-ai/rules/*.mdc"
      memory_type: coding_preference
      memory_scope: workspace
    - glob: "ucx-ai/mermaid-diagrams/*.md"
      memory_type: architecture_decision
      memory_scope: workspace
    - glob: "*/README.md"
      memory_type: project_fact
      memory_scope: project
    - glob: "*/docs/ARCHITECTURE.md"
      memory_type: architecture_decision
      memory_scope: project
    - glob: "*/CLAUDE.md"
      memory_type: coding_preference
      memory_scope: project
    - glob: "*/docs/adr/*.md"
      memory_type: architecture_decision
      memory_scope: project

  # Repos in this workspace (used for scoping)
  repos:
    - name: UCX.UI
    - name: Ucx.CaseDetails
    - name: Ucx.RequestRouting
    - name: ucx.messages
    - name: evicore.gravity.common
    # add remaining repos here
```

## Step 3: Create AGENTS.md

```markdown
# Memory-First Agent Workflow

This workspace uses memory-mcp for durable context across sessions.

## Before Starting Any Task

Call get_context_packet:
  workspace: "ucx-root"
  repo: "<current repo>"
  request: "<your task description>"

Check context_quality and suggested_next_action before reading source files.

## Scoping Convention

Use these parameters consistently:
  workspace: "ucx-root"          (always)
  repo: "<git repo name>"        (per-service work)
  component: "<layer>"           (Api/Application/Domain/Infrastructure/Observer)

## Storing New Memories

When you learn something durable (architecture decision, coding convention,
event contract, key fact), store it:

  add_memory(
    content="<fact>",
    memory_type="<type>",
    memory_scope="<scope>",
    workspace="ucx-root",
    repo="<repo>",
  )

## Event Contracts

For event-sourced facts, use memory_type="event_contract" with metadata:
  {
    "event_name": "...",
    "producers": [...],
    "consumers": [...]
  }

Use get_event_flow(event_name="...") to retrieve producer/consumer context.

## Cross-Service Questions

Use traverse_entity_graph to walk service relationships.
Use search_entities to find services, events, or features by name.
```

## Step 4: Create hooks/pre-session-check.py

```python
#!/usr/bin/env python
"""Pre-session hook: warn if memory store appears empty for this workspace.

Install in Claude Code settings.json:
  "hooks": {
    "SessionStart": [{"command": "python /path/to/pre-session-check.py"}]
  }
"""
import json
import os
import subprocess
import sys

WORKSPACE = os.environ.get("MEMORY_MCP_WORKSPACE", "")
MCP_CMD = os.environ.get("MEMORY_MCP_CMD", "memory-mcp")

if not WORKSPACE:
    sys.exit(0)

try:
    result = subprocess.run(
        [MCP_CMD, "call", "get_memory_cache_state"],
        capture_output=True, text=True, timeout=5,
    )
    state = json.loads(result.stdout)
    memory_count = state.get("total_memories", 0)
    if memory_count < 10:
        print(
            f"[memory-mcp] WARNING: only {memory_count} memories for workspace '{WORKSPACE}'. "
            "Consider running: python scripts/ingest_markdown_workspace.py "
            f"--workspace {WORKSPACE} --dir <workspace-root>",
            file=sys.stderr,
        )
except Exception:
    pass  # hook must not block session start
```

## Step 5: Commit

```bash
git add client-setups/ucx-workspace/
git commit -m "docs(client-setups): add P3 UCX-style workspace hook pack"
```

## Merge

```bash
git checkout main
git merge feat/p3-hook-pack --no-ff -m "docs: add P3 UCX-style workspace client hook pack"
git push origin main
```

## Handoff prompt for Track 12

```
Continue memory-mcp roadmap. Track 11 (P3 hook pack) is complete and merged to main.
Next: Track 12 — read docs/prompts/impl-p3-hosted-mode.md and implement it.
Branch off main as feat/p3-hosted-mode. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 11 status from ⬜ to ✅ before starting Track 12.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-p3-hook-pack.md
git commit -m "docs(prompts): add Track 11 P3 hook pack prompt"
```

---

## Task 14: Create impl-p3-hosted-mode.md

**Files:**
- Create: `docs/prompts/impl-p3-hosted-mode.md`

- [ ] **Step 1: Create the file**

```markdown
# Implementation Prompt — P3 Hosted / Remote Mode Hardening

**Model:** Sonnet
**Estimated effort:** 4–8 hrs
**Branch:** `feat/p3-hosted-mode`

## Context

`MEMORY_MCP_AUTH_MODE=remote` already exists. This track adds the remaining pieces
for a production multi-user deployment: per-tenant workspace isolation enforcement,
rate limiting per workspace, and deployment documentation.

## Relevant files

- Read first: `src/memory_mcp/auth/` (understand current auth layer)
- Modify: `src/memory_mcp/auth/policy.py` — per-tenant isolation
- Modify: `src/memory_mcp/mcp_tools/server.py` — rate limit wrapper
- Create: `docs/hosted_deployment.md` — operator docs
- Test: `tests/test_auth_hosted.py` (new)

## Step 1: Read auth layer

Read `src/memory_mcp/auth/policy.py` and `tests/test_auth_policy.py` in full.
Understand how `AuthAction`, `_authorize_tool_call`, and workspace scoping work.

## Step 2: Per-tenant isolation

In remote mode, every MCP call must carry a `tenant_id` (derived from the auth
token's workspace claim). Add enforcement in `_authorize_tool_call`:

```python
# In remote mode, caller's workspace must match the token's workspace claim
if auth_mode == "remote" and workspace and token_workspace:
    if workspace != token_workspace:
        raise PermissionError(
            f"Workspace mismatch: token grants '{token_workspace}', "
            f"caller requested '{workspace}'"
        )
```

Write tests:
```python
def test_remote_mode_rejects_cross_workspace_access(auth_client):
    """Token for workspace A must not read workspace B."""
    with remote_auth_context(token_workspace="workspace-a"):
        with pytest.raises(PermissionError, match="Workspace mismatch"):
            auth_client.call("search_memory", {
                "query": "test", "workspace": "workspace-b"
            })
```

## Step 3: Rate limiting

Add a simple in-memory rate limiter (token bucket per workspace):

```python
# src/memory_mcp/auth/rate_limit.py
import time
import threading
from collections import defaultdict

_WRITE_LIMIT = int(os.environ.get("MEMORY_MCP_RATE_LIMIT_WRITES_PER_MIN", "60"))
_READ_LIMIT = int(os.environ.get("MEMORY_MCP_RATE_LIMIT_READS_PER_MIN", "300"))

_lock = threading.Lock()
_buckets: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(workspace: str, action: str) -> None:
    """Raise RateLimitError if the workspace exceeds its per-minute limit."""
    limit = _WRITE_LIMIT if action == "write" else _READ_LIMIT
    now = time.monotonic()
    key = f"{workspace}:{action}"
    with _lock:
        timestamps = _buckets[key]
        # Drop entries older than 60 seconds
        _buckets[key] = [t for t in timestamps if now - t < 60]
        if len(_buckets[key]) >= limit:
            raise PermissionError(
                f"Rate limit exceeded for workspace '{workspace}' ({action}): "
                f"{limit} requests/min"
            )
        _buckets[key].append(now)
```

Call `check_rate_limit(workspace, "read" or "write")` in `_authorize_tool_call`
when `MEMORY_MCP_AUTH_MODE=remote`.

## Step 4: Write docs/hosted_deployment.md

Cover:
- Required environment variables for remote mode
- OIDC token configuration
- Rate limit env vars
- Docker Compose production example (no dev volumes)
- Backup recommendation (pg_dump cron)
- Health check endpoint

## Step 5: Run tests

```bash
pytest tests/test_auth_policy.py tests/test_auth_hosted.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p3-hosted-mode --no-ff -m "feat: add P3 hosted mode hardening (isolation, rate limits, docs)"
git push origin main
```

## Handoff — roadmap complete

```
memory-mcp roadmap is complete. All 12 tracks merged to main.
Update ROADMAP.md: change Track 12 status from ⬜ to ✅.
Run: pytest -v
Run: python benchmarks/run_multi_repo_benchmarks.py --seed --report
Commit the final ROADMAP.md update to main.
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/prompts/impl-p3-hosted-mode.md
git commit -m "docs(prompts): add Track 12 P3 hosted mode hardening prompt"
```

---

## Task 15: Final commit and push

- [ ] **Step 1: Verify all prompt files exist**

```bash
ls docs/prompts/
```

Expected output includes:
```
ROADMAP.md
impl-auto-capture.md
impl-semantic-retrieval.md
impl-qw1-markdown-ingest.md
impl-p1-entity-graph.md
impl-p1-code-citations.md
impl-p1-classifier.md
impl-p2-event-flow.md
impl-p2-packet-diagnostics.md
impl-p2-code-graph-import.md
impl-p2-benchmarks.md
impl-p3-hook-pack.md
impl-p3-hosted-mode.md
```

- [ ] **Step 2: Push main to origin**

```bash
git push origin main
```

- [ ] **Step 3: Confirm and provide Track 1 handoff**

```
Track 0 complete. All prompt files committed to main.

To start Track 1, paste this into a fresh session:

---
Continue memory-mcp roadmap. Track 0 (branch cleanup + scaffold) is complete and merged to main.
Next: Track 1 — read docs/prompts/impl-auto-capture.md and implement it.
Branch off main as feat/auto-capture-distillation. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 1 status from ⬜ to ✅ after merging.
---
```
