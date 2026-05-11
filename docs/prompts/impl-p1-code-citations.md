# Implementation Prompt — P1 Code Citations + QW3 cited_path Filter

**Model:** Sonnet
**Estimated effort:** 4–6 hrs
**Branch:** `feat/p1-code-citations`

## Context

Adds a `code_citations` JSONB column to `memories` so a memory can cite specific
files, symbols, or endpoints in the codebase. Also adds a `cited_path` filter to
`search_memory` (QW3 — previously deferred until this column existed).

Track 5 must also update `IngestWriter.upsert` to accept and store `code_citations`
so that Track 9 (code graph import) can pass citations through the writer.

## Relevant files

- Create: `migrations/versions/0007_code_citations.py`
- Modify: `src/memory_mcp/models/schema.py` — add `code_citations` column
- Modify: `src/memory_mcp/ingest/writer.py` — accept `code_citations` in `upsert`
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

## Step 4: Update IngestWriter.upsert to accept code_citations

Read `src/memory_mcp/ingest/writer.py`. Add `code_citations: list[dict] | None = None`
as a parameter to `upsert`. When creating or updating a Memory object, set:

```python
if code_citations is not None:
    memory.code_citations = code_citations
```

## Step 5: Add validator to server.py

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
            raise ValueError(
                f"code_citation path must be relative, got: {path!r} (absolute paths disallowed)"
            )
        if len(path) > 500:
            raise ValueError("code_citation path too long (max 500 chars)")
        kind = c.get("kind", "file")
        if kind not in _VALID_CITATION_KINDS:
            raise ValueError(f"code_citation kind must be one of {sorted(_VALID_CITATION_KINDS)}")
        result.append({k: v for k, v in c.items()})
    return result
```

## Step 6: Add `code_citations` parameter to add_memory and supersede_memory

Add `code_citations: list[dict] | None = None` to both tools.
After `_check_content_for_secrets(content)`:

```python
code_citations = _validate_code_citations(code_citations)
```

Pass `code_citations=code_citations` when constructing or updating the Memory object
(or in the MemoryService call, depending on how add_memory is implemented).

## Step 7: Add `cited_path` filter to search_memory

Add `cited_path: str | None = None` to `search_memory`.
Validate: `cited_path = _validate_text("cited_path", cited_path, max_chars=500)`.

In the retrieval query, if `cited_path` is set, filter using JSONB path existence.
Check how the Memory query is built in `retrieval/service.py` and add:

```python
if cited_path:
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
    from sqlalchemy import cast, func
    q = q.filter(
        func.jsonb_path_exists(
            Memory.code_citations,
            cast(f'$[*] ? (@.path starts with "{cited_path}")', sa.Text),
        )
    )
```

## Step 8: Run migration and tests

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
