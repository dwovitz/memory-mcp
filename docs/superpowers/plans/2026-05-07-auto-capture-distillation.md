# Auto-Capture and Distillation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hook-driven auto-capture of Claude Code session events into a Postgres-backed staging queue, with a background distiller that compresses raw observations into typed scoped memories using model-routed Claude calls; surface them automatically on UserPromptSubmit.

**Architecture:** A new `staging_observations` table in Postgres (no SQLite — multi-client deployment) receives raw events via a new MCP tool `enqueue_observation`. Client-side hooks (PostToolUse, SessionStart, UserPromptSubmit, SessionEnd) call that tool over the existing FastMCP transport. A separate `distiller` worker process polls the queue with `FOR UPDATE SKIP LOCKED`, routes each batch to Haiku (simple tool-only queues) or Sonnet (mixed/complex), prompts the model to emit typed memory dicts, and promotes them through the existing `IngestWriter` (which handles dedupe, scope, lazy embedding). UserPromptSubmit hook calls `get_context_packet` and injects the compressed result into the model's context.

**Tech Stack:** Python 3.11+, Postgres 16 + pgvector, SQLAlchemy, Alembic, FastMCP, Anthropic SDK (`anthropic>=0.40`), pytest, Docker Compose.

---

## File Structure

**Create:**
- `migrations/versions/0010_staging_observations.py` — Alembic migration for the queue table
- `src/memory_mcp/models/staging.py` — `StagingObservation` SQLAlchemy model
- `src/memory_mcp/repositories/staging.py` — `StagingRepository` with enqueue/claim/complete/fail
- `src/memory_mcp/distiller/__init__.py` — package marker
- `src/memory_mcp/distiller/router.py` — model routing (Haiku vs Sonnet) based on payload complexity
- `src/memory_mcp/distiller/prompts.py` — system + user prompt templates for distillation
- `src/memory_mcp/distiller/service.py` — `DistillerService` that claims, distills, promotes
- `src/memory_mcp/distiller/runner.py` — long-running poll loop entrypoint (`python -m memory_mcp.distiller.runner`)
- `hooks/post_tool_use.py` — Claude Code PostToolUse hook (POST observation to MCP)
- `hooks/user_prompt_submit.py` — UserPromptSubmit hook (calls `get_context_packet`, emits additionalContext)
- `hooks/session_start.py` / `hooks/session_end.py` — session boundary markers
- `hooks/_client.py` — shared MCP client helper (HTTP transport)
- `tests/test_staging_repository.py`
- `tests/distiller/test_router.py`
- `tests/distiller/test_service.py`
- `tests/hooks/test_post_tool_use.py`
- `tests/hooks/test_user_prompt_submit.py`
- `docs/auto_capture.md` — operator docs (env vars, hook install, distiller deployment)

**Modify:**
- `src/memory_mcp/mcp_tools/server.py` — add `enqueue_observation` and `get_memory_by_id` tools
- `src/memory_mcp/models/__init__.py` — export `StagingObservation`
- `docker-compose.yml` — add `distiller` service sharing Postgres
- `pyproject.toml` — add `anthropic` dependency
- `README.md` — link to `docs/auto_capture.md`

---

## Task 1: Staging Table Migration

**Files:**
- Create: `migrations/versions/0010_staging_observations.py`
- Test: `tests/test_staging_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_staging_migration.py
from sqlalchemy import inspect

from memory_mcp.db import session_scope


def test_staging_observations_table_exists():
    with session_scope() as session:
        insp = inspect(session.get_bind())
        assert "staging_observations" in insp.get_table_names()
        cols = {c["name"] for c in insp.get_columns("staging_observations")}
        assert {
            "id",
            "source",
            "payload",
            "scope",
            "status",
            "attempts",
            "claimed_at",
            "created_at",
            "completed_at",
            "error_message",
        }.issubset(cols)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_staging_migration.py -v`
Expected: FAIL — `staging_observations` not in table names.

- [ ] **Step 3: Write the migration**

```python
# migrations/versions/0010_staging_observations.py
"""staging_observations queue for raw session events.

Revision ID: 0010_staging_observations
Revises: 0009_<previous>
Create Date: 2026-05-07
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_staging_observations"
down_revision = "0009_<previous>"  # set to current head before committing
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staging_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(64), nullable=False),  # post_tool_use, session_start, ...
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("scope", postgresql.JSONB, nullable=False),  # workspace/project/repo/component
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_staging_obs_pending_created",
        "staging_observations",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_check_constraint(
        "ck_staging_obs_status",
        "staging_observations",
        "status IN ('pending', 'claimed', 'done', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_staging_obs_status", "staging_observations")
    op.drop_index("ix_staging_obs_pending_created", "staging_observations")
    op.drop_table("staging_observations")
```

Before saving, run `alembic heads` and replace `down_revision = "0009_<previous>"` with the actual head id.

- [ ] **Step 4: Apply and verify**

Run: `alembic upgrade head && pytest tests/test_staging_migration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/0010_staging_observations.py tests/test_staging_migration.py
git commit -m "feat(staging): add staging_observations queue table"
```

---

## Task 2: StagingObservation Model

**Files:**
- Create: `src/memory_mcp/models/staging.py`
- Modify: `src/memory_mcp/models/__init__.py`
- Test: `tests/test_staging_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_staging_model.py
from memory_mcp.db import session_scope
from memory_mcp.models import StagingObservation


def test_insert_and_load_staging_observation():
    with session_scope() as s:
        obs = StagingObservation(
            source="post_tool_use",
            payload={"tool": "Edit", "args": {"file": "x.py"}},
            scope={"workspace": "ai", "project": "memory-mcp"},
        )
        s.add(obs)
        s.flush()
        loaded = s.get(StagingObservation, obs.id)
        assert loaded.status == "pending"
        assert loaded.attempts == 0
        assert loaded.payload["tool"] == "Edit"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_staging_model.py -v`
Expected: FAIL — `cannot import name 'StagingObservation'`.

- [ ] **Step 3: Implement model**

```python
# src/memory_mcp/models/staging.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from memory_mcp.models.base import Base


class StagingObservation(Base):
    __tablename__ = "staging_observations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'claimed', 'done', 'failed')",
            name="ck_staging_obs_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Then add to `src/memory_mcp/models/__init__.py`:

```python
from memory_mcp.models.staging import StagingObservation  # noqa: F401
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_staging_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/memory_mcp/models/staging.py src/memory_mcp/models/__init__.py tests/test_staging_model.py
git commit -m "feat(staging): add StagingObservation ORM model"
```

---

## Task 3: StagingRepository (enqueue + claim with SKIP LOCKED)

**Files:**
- Create: `src/memory_mcp/repositories/staging.py`
- Test: `tests/test_staging_repository.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_staging_repository.py
from memory_mcp.db import session_scope
from memory_mcp.repositories.staging import StagingRepository


def test_enqueue_returns_id_and_pending():
    with session_scope() as s:
        repo = StagingRepository(s)
        obs_id = repo.enqueue(
            source="post_tool_use",
            payload={"tool": "Read"},
            scope={"workspace": "ai", "project": "memory-mcp"},
        )
        s.flush()
        rows = repo.peek_pending(limit=10)
        assert any(r.id == obs_id and r.status == "pending" for r in rows)


def test_claim_batch_marks_claimed_and_skips_already_claimed():
    with session_scope() as s:
        repo = StagingRepository(s)
        ids = [
            repo.enqueue("post_tool_use", {"i": i}, {"project": "memory-mcp"})
            for i in range(3)
        ]
        s.commit()
        first = repo.claim_batch(limit=2, worker_id="w1")
        assert len(first) == 2
        assert all(r.status == "claimed" for r in first)
        second = repo.claim_batch(limit=10, worker_id="w2")
        assert len(second) == 1
        assert second[0].id == ids[2]


def test_mark_done_and_failed():
    with session_scope() as s:
        repo = StagingRepository(s)
        obs_id = repo.enqueue("post_tool_use", {}, {"project": "memory-mcp"})
        s.commit()
        claimed = repo.claim_batch(limit=1, worker_id="w1")
        repo.mark_done(claimed[0].id)
        s.commit()

        obs_id2 = repo.enqueue("post_tool_use", {}, {"project": "memory-mcp"})
        s.commit()
        claimed2 = repo.claim_batch(limit=1, worker_id="w1")
        repo.mark_failed(claimed2[0].id, "boom")
        s.commit()

        assert s.get(type(claimed[0]), obs_id).status == "done"
        failed = s.get(type(claimed[0]), obs_id2)
        assert failed.status == "failed"
        assert failed.error_message == "boom"
        assert failed.attempts == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_staging_repository.py -v`
Expected: FAIL — `cannot import StagingRepository`.

- [ ] **Step 3: Implement repository**

```python
# src/memory_mcp/repositories/staging.py
from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from memory_mcp.models import StagingObservation


class StagingRepository:
    """Postgres-backed FIFO queue for raw session observations."""

    def __init__(self, session: Session) -> None:
        self._s = session

    def enqueue(self, source: str, payload: dict, scope: dict) -> uuid.UUID:
        obs = StagingObservation(source=source, payload=payload, scope=scope)
        self._s.add(obs)
        self._s.flush()
        return obs.id

    def peek_pending(self, *, limit: int = 50) -> Sequence[StagingObservation]:
        stmt = (
            select(StagingObservation)
            .where(StagingObservation.status == "pending")
            .order_by(StagingObservation.created_at)
            .limit(limit)
        )
        return self._s.execute(stmt).scalars().all()

    def claim_batch(self, *, limit: int, worker_id: str) -> Sequence[StagingObservation]:
        # SELECT ... FOR UPDATE SKIP LOCKED is the standard distributed-queue
        # primitive in Postgres; multiple workers can claim disjoint batches
        # without coordination.
        stmt = (
            select(StagingObservation.id)
            .where(StagingObservation.status == "pending")
            .order_by(StagingObservation.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        ids = list(self._s.execute(stmt).scalars().all())
        if not ids:
            return []
        now = datetime.now(timezone.utc)
        self._s.execute(
            update(StagingObservation)
            .where(StagingObservation.id.in_(ids))
            .values(status="claimed", claimed_at=now)
        )
        self._s.flush()
        return self._s.execute(
            select(StagingObservation).where(StagingObservation.id.in_(ids))
        ).scalars().all()

    def mark_done(self, obs_id: uuid.UUID) -> None:
        self._s.execute(
            update(StagingObservation)
            .where(StagingObservation.id == obs_id)
            .values(status="done", completed_at=datetime.now(timezone.utc))
        )

    def mark_failed(self, obs_id: uuid.UUID, error: str) -> None:
        self._s.execute(
            update(StagingObservation)
            .where(StagingObservation.id == obs_id)
            .values(
                status="failed",
                error_message=error,
                attempts=StagingObservation.attempts + 1,
                completed_at=datetime.now(timezone.utc),
            )
        )
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/test_staging_repository.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/memory_mcp/repositories/staging.py tests/test_staging_repository.py
git commit -m "feat(staging): repository with SKIP LOCKED claim_batch"
```

---

## Task 4: MCP `enqueue_observation` Tool

**Files:**
- Modify: `src/memory_mcp/mcp_tools/server.py`
- Test: `tests/mcp_tools/test_enqueue_observation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp_tools/test_enqueue_observation.py
from memory_mcp.mcp_tools.server import enqueue_observation
from memory_mcp.db import session_scope
from memory_mcp.repositories.staging import StagingRepository


def test_enqueue_observation_returns_id_and_persists():
    result = enqueue_observation(
        source="post_tool_use",
        payload={"tool": "Edit", "file": "x.py"},
        workspace="ai",
        project="memory-mcp",
        repo="memory-mcp",
        component=None,
    )
    assert "observation_id" in result
    with session_scope() as s:
        repo = StagingRepository(s)
        rows = repo.peek_pending(limit=20)
    assert any(str(r.id) == result["observation_id"] for r in rows)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/mcp_tools/test_enqueue_observation.py -v`
Expected: FAIL — `cannot import enqueue_observation`.

- [ ] **Step 3: Add tool to server**

Append to `src/memory_mcp/mcp_tools/server.py` (after existing tool definitions, follow the file's existing `@mcp.tool()` decorator pattern):

```python
from memory_mcp.repositories.staging import StagingRepository


@mcp.tool()
def enqueue_observation(
    source: str,
    payload: dict[str, Any],
    workspace: str | None = None,
    project: str | None = None,
    repo: str | None = None,
    component: str | None = None,
) -> dict[str, str]:
    """Enqueue a raw session observation for background distillation.

    Called by Claude Code hooks. Returns immediately; the distiller worker
    promotes raw observations into typed memories asynchronously.
    """
    scope = {k: v for k, v in {
        "workspace": workspace,
        "project": project,
        "repo": repo,
        "component": component,
    }.items() if v is not None}
    with session_scope() as s:
        repo_ = StagingRepository(s)
        obs_id = repo_.enqueue(source=source, payload=payload, scope=scope)
        s.commit()
    return {"observation_id": str(obs_id)}


@mcp.tool()
def get_memory_by_id(memory_id: str) -> dict[str, Any]:
    """Fetch a single memory by UUID for citation/dereferencing.

    Returns content, scope, type, confidence, and tags. Used by clients
    that received a memory id in a context packet and want full detail.
    """
    with session_scope() as s:
        m = s.get(Memory, UUID(memory_id))
        if m is None or m.archived_at is not None:
            return {"error": "not_found", "id": memory_id}
        return {
            "id": str(m.id),
            "content": m.content,
            "type": m.memory_type,
            "scope": m.applies_to,
            "confidence": float(m.confidence) if m.confidence is not None else None,
            "tags": [t.tag for t in m.tags],
        }
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/mcp_tools/test_enqueue_observation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/memory_mcp/mcp_tools/server.py tests/mcp_tools/test_enqueue_observation.py
git commit -m "feat(mcp): add enqueue_observation and get_memory_by_id tools"
```

---

## Task 5: Distiller Model Router

**Files:**
- Create: `src/memory_mcp/distiller/__init__.py` (empty)
- Create: `src/memory_mcp/distiller/router.py`
- Test: `tests/distiller/test_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/distiller/test_router.py
from memory_mcp.distiller.router import select_model, ModelChoice


def test_tool_only_simple_routes_to_haiku():
    batch = [
        {"source": "post_tool_use", "payload": {"tool": "Read"}},
        {"source": "post_tool_use", "payload": {"tool": "Glob"}},
    ]
    assert select_model(batch) is ModelChoice.HAIKU


def test_mixed_with_user_prompt_routes_to_sonnet():
    batch = [
        {"source": "user_prompt_submit", "payload": {"text": "design auth"}},
        {"source": "post_tool_use", "payload": {"tool": "Edit"}},
    ]
    assert select_model(batch) is ModelChoice.SONNET


def test_large_payload_routes_to_sonnet():
    batch = [
        {"source": "post_tool_use",
         "payload": {"tool": "Edit", "diff": "x" * 20_000}},
    ]
    assert select_model(batch) is ModelChoice.SONNET
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/distiller/test_router.py -v`
Expected: FAIL — `cannot import select_model`.

- [ ] **Step 3: Implement router**

```python
# src/memory_mcp/distiller/router.py
from __future__ import annotations

import enum
import json
from collections.abc import Sequence
from typing import Any

# Read-only / cheap tools — pure observation, low reasoning needed.
_SIMPLE_TOOLS = {"Read", "Glob", "Grep", "Bash", "WebFetch", "WebSearch"}
_SIZE_THRESHOLD_BYTES = 10_000


class ModelChoice(str, enum.Enum):
    HAIKU = "claude-haiku-4-5-20251001"
    SONNET = "claude-sonnet-4-6"


def select_model(batch: Sequence[dict[str, Any]]) -> ModelChoice:
    """Pick the cheapest adequate model for a distillation batch.

    Heuristics (mirrors claude-mem's complexity-based routing):
    - Any user_prompt_submit or session_end event -> Sonnet (semantic reasoning).
    - Any payload over _SIZE_THRESHOLD_BYTES -> Sonnet (long context).
    - Tool-only batch with all simple/read tools -> Haiku.
    - Otherwise -> Sonnet.
    """
    for obs in batch:
        source = obs.get("source", "")
        if source in {"user_prompt_submit", "session_end"}:
            return ModelChoice.SONNET
        payload = obs.get("payload", {})
        if len(json.dumps(payload, default=str)) > _SIZE_THRESHOLD_BYTES:
            return ModelChoice.SONNET
        tool = payload.get("tool")
        if source == "post_tool_use" and tool not in _SIMPLE_TOOLS:
            return ModelChoice.SONNET
    return ModelChoice.HAIKU
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/distiller/test_router.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/memory_mcp/distiller/__init__.py src/memory_mcp/distiller/router.py tests/distiller/test_router.py
git commit -m "feat(distiller): complexity-based Haiku/Sonnet model router"
```

---

## Task 6: Distiller Prompts

**Files:**
- Create: `src/memory_mcp/distiller/prompts.py`
- Test: `tests/distiller/test_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/distiller/test_prompts.py
import json

from memory_mcp.distiller.prompts import build_distillation_messages


def test_messages_include_observations_and_scope():
    batch = [
        {"source": "post_tool_use",
         "payload": {"tool": "Edit", "file": "src/x.py"},
         "scope": {"workspace": "ai", "project": "memory-mcp"}},
    ]
    system, user = build_distillation_messages(batch)
    assert "JSON array" in system
    assert "memory_type" in system
    body = json.loads(user) if user.lstrip().startswith("[") else user
    assert "src/x.py" in user
    assert "memory-mcp" in user
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/distiller/test_prompts.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement prompts**

```python
# src/memory_mcp/distiller/prompts.py
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

_SYSTEM = """You are a memory distillation assistant for a developer tool.

Input: a JSON array of raw session observations (tool calls, prompts, summaries).
Output: a JSON array of compact, durable memory entries. Each entry MUST be a
JSON object with these fields:

  - memory_type: one of [project_fact, architecture_decision, coding_preference,
    workflow_location, dependency, project_rule, external_reference,
    component_summary, app_knowledge].
  - content: 1-3 sentences. Write a durable claim, not a play-by-play.
  - confidence: 0.0-1.0.
  - tags: array of short kebab-case tags.
  - applies_to: object with workspace/project/repo/component (use only the
    fields present in the input scope; omit unknown layers).
  - ingest_key: a deterministic short string derived from content+scope so
    re-runs dedupe (e.g. "distill:<sha8 of content>").

Rules:
- DROP ephemeral details: in-progress task state, file paths that were merely
  read, transient errors that were resolved.
- KEEP decisions, established patterns, discovered constraints, completed
  milestones, named external references.
- Emit an empty array [] if nothing in the batch is durable.
- Output ONLY the JSON array, no prose, no code fence.
"""


def build_distillation_messages(batch: Sequence[dict[str, Any]]) -> tuple[str, str]:
    """Return (system, user) message strings for the distiller."""
    user = json.dumps(list(batch), default=str, indent=2)
    return _SYSTEM, user
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/distiller/test_prompts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/memory_mcp/distiller/prompts.py tests/distiller/test_prompts.py
git commit -m "feat(distiller): distillation prompt builder"
```

---

## Task 7: DistillerService — claim, distill, promote

**Files:**
- Create: `src/memory_mcp/distiller/service.py`
- Modify: `pyproject.toml` (add `anthropic` dep)
- Test: `tests/distiller/test_service.py`

- [ ] **Step 1: Add Anthropic dependency**

Edit `pyproject.toml` and add to the `dependencies` array:

```toml
"anthropic>=0.40,<1.0",
```

Then `pip install -e .`.

- [ ] **Step 2: Write the failing test (with a fake Anthropic client)**

```python
# tests/distiller/test_service.py
import json
from unittest.mock import MagicMock

import pytest

from memory_mcp.db import session_scope
from memory_mcp.distiller.service import DistillerService
from memory_mcp.repositories.staging import StagingRepository
from memory_mcp.repositories.memories import MemoriesRepository


class _FakeClient:
    def __init__(self, response_json: list[dict]):
        self._response = response_json
        self.calls = []

    @property
    def messages(self):
        outer = self
        class _Messages:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return MagicMock(content=[MagicMock(text=json.dumps(outer._response))])
        return _Messages()


def test_distill_once_promotes_durable_memories():
    with session_scope() as s:
        StagingRepository(s).enqueue(
            "post_tool_use",
            {"tool": "Edit", "file": "src/auth.py", "decision": "use OIDC"},
            {"workspace": "ai", "project": "memory-mcp"},
        )
        s.commit()

    fake = _FakeClient([{
        "memory_type": "architecture_decision",
        "content": "Auth uses OIDC for memory-mcp.",
        "confidence": 0.9,
        "tags": ["auth", "oidc"],
        "applies_to": {"workspace": "ai", "project": "memory-mcp"},
        "ingest_key": "distill:auth-oidc-1",
    }])
    svc = DistillerService(client=fake, worker_id="test-w")
    processed = svc.distill_once(batch_size=10)

    assert processed >= 1
    with session_scope() as s:
        repo = MemoriesRepository(s)
        match = repo.find_active_by_metadata_key("ingest_key", "distill:auth-oidc-1")
        assert match is not None
        assert "OIDC" in match.content


def test_distill_once_marks_failed_on_invalid_json():
    with session_scope() as s:
        StagingRepository(s).enqueue(
            "post_tool_use", {"tool": "Edit"}, {"project": "memory-mcp"})
        s.commit()

    fake = MagicMock()
    fake.messages.create.return_value = MagicMock(content=[MagicMock(text="not json")])
    svc = DistillerService(client=fake, worker_id="test-w")
    svc.distill_once(batch_size=10)

    with session_scope() as s:
        from memory_mcp.models import StagingObservation
        from sqlalchemy import select
        rows = s.execute(select(StagingObservation)).scalars().all()
        assert any(r.status == "failed" for r in rows)
```

- [ ] **Step 3: Run to verify failure**

Run: `pytest tests/distiller/test_service.py -v`
Expected: FAIL — service module missing.

- [ ] **Step 4: Implement service**

```python
# src/memory_mcp/distiller/service.py
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Protocol

from memory_mcp.db import session_scope
from memory_mcp.distiller.prompts import build_distillation_messages
from memory_mcp.distiller.router import ModelChoice, select_model
from memory_mcp.ingest.writer import IngestWriter
from memory_mcp.repositories.staging import StagingRepository
from memory_mcp.services.memory_service import MemoryService

log = logging.getLogger(__name__)


class _AnthropicLike(Protocol):
    @property
    def messages(self) -> Any: ...


class DistillerService:
    """Polls staging_observations, distills batches, promotes typed memories."""

    def __init__(self, *, client: _AnthropicLike, worker_id: str,
                 max_tokens: int = 4096) -> None:
        self._client = client
        self._worker_id = worker_id
        self._max_tokens = max_tokens

    def distill_once(self, *, batch_size: int = 25) -> int:
        """Process at most one batch. Returns number of staging rows handled."""
        with session_scope() as s:
            staging = StagingRepository(s)
            rows = staging.claim_batch(limit=batch_size, worker_id=self._worker_id)
            if not rows:
                return 0
            batch = [
                {"source": r.source, "payload": r.payload, "scope": r.scope}
                for r in rows
            ]
            row_ids = [r.id for r in rows]
            s.commit()  # release row locks before the LLM call

        model = select_model(batch)
        system, user = build_distillation_messages(batch)
        try:
            resp = self._client.messages.create(
                model=model.value,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = resp.content[0].text
            entries = json.loads(text)
            if not isinstance(entries, list):
                raise ValueError(f"expected list, got {type(entries).__name__}")
        except Exception as exc:
            log.warning("distillation failed for %d rows: %s", len(row_ids), exc)
            with session_scope() as s:
                staging = StagingRepository(s)
                for rid in row_ids:
                    staging.mark_failed(rid, str(exc)[:500])
                s.commit()
            return len(row_ids)

        # Promote entries via IngestWriter (handles dedupe + scope routing).
        with session_scope() as s:
            writer = IngestWriter(MemoryService(session=s))
            normalized = [self._normalize(e) for e in entries]
            writer.upsert_memories(normalized)
            staging = StagingRepository(s)
            for rid in row_ids:
                staging.mark_done(rid)
            s.commit()
        return len(row_ids)

    @staticmethod
    def _normalize(entry: dict) -> dict:
        # Ensure ingest_key exists; derive from content+scope hash if missing.
        if "ingest_key" not in entry:
            payload = json.dumps(
                {"c": entry.get("content", ""), "s": entry.get("applies_to", {})},
                sort_keys=True,
            )
            entry["ingest_key"] = (
                "distill:" + hashlib.sha256(payload.encode()).hexdigest()[:16]
            )
        return entry
```

- [ ] **Step 5: Verify pass**

Run: `pytest tests/distiller/test_service.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/memory_mcp/distiller/service.py tests/distiller/test_service.py
git commit -m "feat(distiller): claim/distill/promote service with Anthropic client"
```

---

## Task 8: Distiller Runner (long-running poll loop)

**Files:**
- Create: `src/memory_mcp/distiller/runner.py`
- Test: `tests/distiller/test_runner_smoke.py`

- [ ] **Step 1: Write the smoke test**

```python
# tests/distiller/test_runner_smoke.py
from unittest.mock import MagicMock, patch

from memory_mcp.distiller.runner import run_loop


def test_run_loop_stops_on_shutdown_event():
    svc = MagicMock()
    svc.distill_once.side_effect = [0, 0, 0]
    stop = MagicMock()
    # First two checks: not set; third: set -> exit.
    stop.is_set.side_effect = [False, False, True]
    stop.wait.return_value = None
    run_loop(svc, stop_event=stop, idle_sleep=0.01)
    assert svc.distill_once.call_count == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/distiller/test_runner_smoke.py -v`
Expected: FAIL — `cannot import run_loop`.

- [ ] **Step 3: Implement runner**

```python
# src/memory_mcp/distiller/runner.py
from __future__ import annotations

import logging
import os
import signal
import socket
import threading

from anthropic import Anthropic

from memory_mcp.distiller.service import DistillerService

log = logging.getLogger(__name__)


def run_loop(service: DistillerService, *, stop_event: threading.Event,
             idle_sleep: float = 2.0, busy_sleep: float = 0.0) -> None:
    """Poll the staging queue until stop_event is set."""
    while not stop_event.is_set():
        try:
            processed = service.distill_once()
        except Exception:  # noqa: BLE001
            log.exception("distill_once raised; backing off")
            stop_event.wait(idle_sleep)
            continue
        stop_event.wait(busy_sleep if processed > 0 else idle_sleep)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    client = Anthropic()  # picks up ANTHROPIC_API_KEY from env
    service = DistillerService(client=client, worker_id=worker_id)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    log.info("distiller worker %s starting", worker_id)
    run_loop(service, stop_event=stop)
    log.info("distiller worker %s exiting", worker_id)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/distiller/test_runner_smoke.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/memory_mcp/distiller/runner.py tests/distiller/test_runner_smoke.py
git commit -m "feat(distiller): runner with graceful shutdown"
```

---

## Task 9: Hook Client Helper

**Files:**
- Create: `hooks/__init__.py` (empty)
- Create: `hooks/_client.py`
- Test: `tests/hooks/test_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/hooks/test_client.py
from unittest.mock import patch

from hooks._client import enqueue


def test_enqueue_posts_to_configured_url():
    with patch("hooks._client._http_post") as post:
        post.return_value = {"observation_id": "abc"}
        result = enqueue(
            source="post_tool_use",
            payload={"tool": "Edit"},
            scope={"workspace": "ai", "project": "memory-mcp"},
            base_url="http://memory-mcp.local:8765",
        )
        assert result["observation_id"] == "abc"
        post.assert_called_once()
        url, body = post.call_args.args
        assert url.endswith("/tool/enqueue_observation")
        assert body["payload"]["tool"] == "Edit"


def test_enqueue_swallows_network_errors():
    with patch("hooks._client._http_post", side_effect=OSError("down")):
        # Hook must NEVER block the user's session on memory-mcp being down.
        result = enqueue(
            source="post_tool_use",
            payload={},
            scope={},
            base_url="http://invalid.local",
        )
        assert result == {"observation_id": None}
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/hooks/test_client.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement client**

```python
# hooks/_client.py
"""Tiny HTTP client used by Claude Code hooks to talk to memory-mcp.

Hooks run in the user's interactive session; failures here MUST NOT block.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

DEFAULT_BASE_URL = os.environ.get("MEMORY_MCP_HOOK_URL", "http://127.0.0.1:8765")
TIMEOUT_SECONDS = 1.5


def _http_post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # noqa: S310
        return json.loads(resp.read())


def enqueue(*, source: str, payload: dict, scope: dict,
            base_url: str | None = None) -> dict[str, Any]:
    """POST a raw observation. Returns {"observation_id": <id|None>}."""
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    url = f"{base}/tool/enqueue_observation"
    body = {"source": source, "payload": payload, **scope}
    try:
        return _http_post(url, body)
    except Exception:  # noqa: BLE001 — hooks must never raise to the session
        return {"observation_id": None}
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/hooks/test_client.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add hooks/__init__.py hooks/_client.py tests/hooks/test_client.py
git commit -m "feat(hooks): non-blocking HTTP client for memory-mcp"
```

---

## Task 10: PostToolUse Hook

**Files:**
- Create: `hooks/post_tool_use.py`
- Test: `tests/hooks/test_post_tool_use.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/hooks/test_post_tool_use.py
import io
import json
from unittest.mock import patch

from hooks.post_tool_use import main


def test_main_reads_stdin_event_and_enqueues(monkeypatch):
    event = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/x.py"},
        "tool_response": {"success": True},
        "cwd": "/repo/memory-mcp",
        "session_id": "abc123",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    monkeypatch.setenv("MEMORY_MCP_WORKSPACE", "ai")
    monkeypatch.setenv("MEMORY_MCP_PROJECT", "memory-mcp")

    with patch("hooks.post_tool_use.enqueue") as enq:
        enq.return_value = {"observation_id": "id1"}
        rc = main()
    assert rc == 0
    enq.assert_called_once()
    kwargs = enq.call_args.kwargs
    assert kwargs["source"] == "post_tool_use"
    assert kwargs["payload"]["tool"] == "Edit"
    assert kwargs["scope"]["project"] == "memory-mcp"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/hooks/test_post_tool_use.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement hook**

```python
# hooks/post_tool_use.py
"""Claude Code PostToolUse hook -> enqueue observation."""
from __future__ import annotations

import json
import os
import sys

from hooks._client import enqueue


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0

    payload = {
        "tool": event.get("tool_name"),
        "input": event.get("tool_input"),
        "response_summary": _summarize_response(event.get("tool_response")),
        "session_id": event.get("session_id"),
        "cwd": event.get("cwd"),
    }
    scope = {
        k: v for k, v in {
            "workspace": os.environ.get("MEMORY_MCP_WORKSPACE"),
            "project": os.environ.get("MEMORY_MCP_PROJECT"),
            "repo": os.environ.get("MEMORY_MCP_REPO"),
            "component": os.environ.get("MEMORY_MCP_COMPONENT"),
        }.items() if v
    }
    enqueue(source="post_tool_use", payload=payload, scope=scope)
    return 0


def _summarize_response(resp: object) -> object:
    # Truncate large tool_response bodies; full content lives in the staging row
    # only briefly and we don't want to ship megabytes per call.
    text = json.dumps(resp, default=str)
    if len(text) > 4000:
        return text[:4000] + "...<truncated>"
    return resp


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/hooks/test_post_tool_use.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/post_tool_use.py tests/hooks/test_post_tool_use.py
git commit -m "feat(hooks): PostToolUse capture hook"
```

---

## Task 11: SessionStart and SessionEnd Hooks

**Files:**
- Create: `hooks/session_start.py`, `hooks/session_end.py`
- Test: `tests/hooks/test_session_hooks.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/hooks/test_session_hooks.py
import io
import json
from unittest.mock import patch

import hooks.session_start as ss
import hooks.session_end as se


def test_session_start_enqueues(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": "s1"})))
    monkeypatch.setenv("MEMORY_MCP_PROJECT", "memory-mcp")
    with patch("hooks.session_start.enqueue") as enq:
        ss.main()
    assert enq.call_args.kwargs["source"] == "session_start"


def test_session_end_enqueues(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"session_id": "s1"})))
    monkeypatch.setenv("MEMORY_MCP_PROJECT", "memory-mcp")
    with patch("hooks.session_end.enqueue") as enq:
        se.main()
    assert enq.call_args.kwargs["source"] == "session_end"
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/hooks/test_session_hooks.py -v`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement both hooks**

```python
# hooks/session_start.py
from __future__ import annotations

import json
import os
import sys

from hooks._client import enqueue


def _scope() -> dict:
    return {
        k: v for k, v in {
            "workspace": os.environ.get("MEMORY_MCP_WORKSPACE"),
            "project": os.environ.get("MEMORY_MCP_PROJECT"),
            "repo": os.environ.get("MEMORY_MCP_REPO"),
            "component": os.environ.get("MEMORY_MCP_COMPONENT"),
        }.items() if v
    }


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        event = {}
    enqueue(source="session_start",
            payload={"session_id": event.get("session_id")},
            scope=_scope())
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

```python
# hooks/session_end.py
from __future__ import annotations

import json
import os
import sys

from hooks._client import enqueue


def _scope() -> dict:
    return {
        k: v for k, v in {
            "workspace": os.environ.get("MEMORY_MCP_WORKSPACE"),
            "project": os.environ.get("MEMORY_MCP_PROJECT"),
            "repo": os.environ.get("MEMORY_MCP_REPO"),
            "component": os.environ.get("MEMORY_MCP_COMPONENT"),
        }.items() if v
    }


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        event = {}
    enqueue(source="session_end",
            payload={"session_id": event.get("session_id"),
                     "summary": event.get("summary")},
            scope=_scope())
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/hooks/test_session_hooks.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add hooks/session_start.py hooks/session_end.py tests/hooks/test_session_hooks.py
git commit -m "feat(hooks): session_start and session_end capture hooks"
```

---

## Task 12: UserPromptSubmit Hook with Auto-Context Injection

**Files:**
- Create: `hooks/user_prompt_submit.py`
- Test: `tests/hooks/test_user_prompt_submit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/hooks/test_user_prompt_submit.py
import io
import json
from unittest.mock import patch

from hooks.user_prompt_submit import main


def test_emits_additional_context_block_from_packet(monkeypatch, capsys):
    event = {"prompt": "How does auth work?", "session_id": "s1"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(event)))
    monkeypatch.setenv("MEMORY_MCP_PROJECT", "memory-mcp")

    fake_packet = {"rendered": "## Facts\n- Auth uses OIDC.\n",
                   "context_quality": "strong"}
    with patch("hooks.user_prompt_submit._fetch_packet", return_value=fake_packet), \
         patch("hooks.user_prompt_submit.enqueue", return_value={"observation_id": "id"}):
        rc = main()

    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "Auth uses OIDC" in payload["hookSpecificOutput"]["additionalContext"]
```

- [ ] **Step 2: Verify failure**

Run: `pytest tests/hooks/test_user_prompt_submit.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement hook**

```python
# hooks/user_prompt_submit.py
"""UserPromptSubmit hook: enqueue prompt + inject relevant memory context."""
from __future__ import annotations

import json
import os
import sys

from hooks._client import _http_post, DEFAULT_BASE_URL, enqueue


def _scope() -> dict:
    return {
        k: v for k, v in {
            "workspace": os.environ.get("MEMORY_MCP_WORKSPACE"),
            "project": os.environ.get("MEMORY_MCP_PROJECT"),
            "repo": os.environ.get("MEMORY_MCP_REPO"),
            "component": os.environ.get("MEMORY_MCP_COMPONENT"),
        }.items() if v
    }


def _fetch_packet(*, request: str, scope: dict, base_url: str) -> dict | None:
    try:
        return _http_post(
            f"{base_url.rstrip('/')}/tool/get_context_packet",
            {"request": request, "max_tokens": 1200, **scope},
        )
    except Exception:  # noqa: BLE001 — never block the prompt
        return None


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        event = {}

    prompt = event.get("prompt", "")
    scope = _scope()

    # Fire-and-forget: capture this prompt for later distillation.
    enqueue(source="user_prompt_submit",
            payload={"text": prompt[:4000], "session_id": event.get("session_id")},
            scope=scope)

    packet = _fetch_packet(
        request=prompt,
        scope=scope,
        base_url=os.environ.get("MEMORY_MCP_HOOK_URL", DEFAULT_BASE_URL),
    )
    additional = packet.get("rendered", "") if packet else ""

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Verify pass**

Run: `pytest tests/hooks/test_user_prompt_submit.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/user_prompt_submit.py tests/hooks/test_user_prompt_submit.py
git commit -m "feat(hooks): UserPromptSubmit auto-context via get_context_packet"
```

---

## Task 13: Docker Compose — Distiller Service

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add a `distiller` service**

Append to `docker-compose.yml`:

```yaml
  distiller:
    build:
      context: .
    env_file:
      - .env
    environment:
      POSTGRES_HOST: postgres
      LOG_LEVEL: INFO
    command: ["python", "-m", "memory_mcp.distiller.runner"]
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
```

- [ ] **Step 2: Verify it boots and idle-loops**

Run: `docker compose up -d distiller && docker compose logs --since 30s distiller`
Expected output contains: `distiller worker <host>:<pid> starting`.

Then run: `docker compose ps distiller`
Expected: status `running` (not crashing).

- [ ] **Step 3: End-to-end smoke test**

Run from your host (with the MCP server up):

```bash
python -c "from hooks._client import enqueue; \
print(enqueue(source='post_tool_use', \
              payload={'tool':'Edit','file':'x.py','decision':'use OIDC'}, \
              scope={'workspace':'ai','project':'memory-mcp'}))"
```

Wait ~5 seconds, then:

```bash
docker compose exec memory-mcp python -c "
from memory_mcp.db import session_scope
from memory_mcp.models import StagingObservation
from sqlalchemy import select
with session_scope() as s:
    for r in s.execute(select(StagingObservation).order_by(StagingObservation.created_at.desc()).limit(3)).scalars():
        print(r.id, r.status, r.source)
"
```

Expected: at least one row with `status=done` (or `failed` with a clear error in `error_message`).

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(deploy): add distiller worker service"
```

---

## Task 14: Operator Documentation

**Files:**
- Create: `docs/auto_capture.md`
- Modify: `README.md`

- [ ] **Step 1: Write `docs/auto_capture.md`**

```markdown
# Auto-Capture and Distillation

memory-mcp can automatically capture Claude Code session events and distill
them into typed memories without manual `add_memory` calls.

## Architecture

```
Claude Code session
   ├─ PostToolUse hook ─┐
   ├─ UserPromptSubmit ─┼─► HTTP POST /tool/enqueue_observation
   ├─ SessionStart   ───┤        (MCP server, FastMCP HTTP transport)
   └─ SessionEnd     ───┘
                              │
                              ▼
                  Postgres: staging_observations (FOR UPDATE SKIP LOCKED)
                              │
                              ▼
                  distiller worker(s) — Haiku/Sonnet routed
                              │
                              ▼
                  IngestWriter ─► memories table (typed, scoped, deduped)
```

Multiple distiller workers can run concurrently; `claim_batch` uses
`SELECT ... FOR UPDATE SKIP LOCKED` so they never collide. UserPromptSubmit
also pulls a `get_context_packet` and injects it into the model context, so
durable knowledge surfaces automatically without the model having to call
`get_context_packet` itself.

## Server-Side Setup

1. `alembic upgrade head` to create `staging_observations`.
2. `docker compose up -d distiller` to start the worker.
3. Ensure the MCP server exposes the FastMCP HTTP transport on a known port
   (default `8765`). Set `ANTHROPIC_API_KEY` in the distiller's environment.

## Client-Side Setup

In `~/.claude/settings.json` (or per-project `.claude/settings.json`):

```json
{
  "hooks": {
    "PostToolUse": [{"command": "python /path/to/memory-mcp/hooks/post_tool_use.py"}],
    "UserPromptSubmit": [{"command": "python /path/to/memory-mcp/hooks/user_prompt_submit.py"}],
    "SessionStart": [{"command": "python /path/to/memory-mcp/hooks/session_start.py"}],
    "SessionEnd": [{"command": "python /path/to/memory-mcp/hooks/session_end.py"}]
  },
  "env": {
    "MEMORY_MCP_HOOK_URL": "http://memory-mcp.local:8765",
    "MEMORY_MCP_WORKSPACE": "ai",
    "MEMORY_MCP_PROJECT": "memory-mcp",
    "MEMORY_MCP_REPO": "memory-mcp"
  }
}
```

Hooks are non-blocking; if the server is unreachable they swallow the
error and return immediately so the user's session is never affected.

## Observability

- Pending queue depth: `SELECT count(*) FROM staging_observations WHERE status='pending';`
- Failed batches: `SELECT id, error_message FROM staging_observations WHERE status='failed' ORDER BY completed_at DESC LIMIT 20;`
- Distillation throughput: distiller logs one INFO line per batch.

## Cost Notes

Routing in `distiller/router.py`:
- Read-only / simple tools (`Read`, `Glob`, `Grep`) -> Haiku.
- Anything involving `user_prompt_submit`, `session_end`, payloads
  >10 KB, or write tools (`Edit`, `Write`) -> Sonnet.

Adjust `_SIMPLE_TOOLS` and `_SIZE_THRESHOLD_BYTES` to tune cost.
```

- [ ] **Step 2: Add a link in `README.md`**

Find the existing docs section (or just append a "Features" item) and add:

```markdown
- **Auto-capture**: hook-driven session ingestion with background distillation —
  see [docs/auto_capture.md](docs/auto_capture.md).
```

- [ ] **Step 3: Commit**

```bash
git add docs/auto_capture.md README.md
git commit -m "docs: auto-capture and distillation guide"
```

---

## Task 15: Memory Refresh

**Files:** none (memory only)

- [ ] **Step 1: Store architectural decisions via `add_memory`**

Run inside any Claude Code session attached to this project:

```
Use add_memory to store these project_facts (workspace=ai, project=memory-mcp,
repo=memory-mcp):

1. "memory-mcp uses a Postgres-backed staging_observations queue with
    FOR UPDATE SKIP LOCKED semantics for distributed worker claiming."
2. "Distillation routes batches to Haiku (simple/read-only tool calls) or
    Sonnet (writes, prompts, large payloads), mirroring claude-mem's
    cost-optimization heuristic."
3. "Claude Code hooks (PostToolUse, UserPromptSubmit, SessionStart,
    SessionEnd) POST to memory-mcp's FastMCP HTTP transport and are
    non-blocking — failures are swallowed so user sessions are never
    affected by memory-mcp downtime."
4. "UserPromptSubmit hook auto-injects get_context_packet output as
    additionalContext, replacing reliance on the model remembering to call
    get_context_packet itself."
```

- [ ] **Step 2: Confirm in next session**

After restart, run `get_context_packet` for `project=memory-mcp` and verify
the four facts appear under `## Facts`. No commit needed.

---

## Self-Review Checklist

- **Spec coverage:** all 7 borrowed claude-mem ideas from the prior analysis are
  covered: hook auto-capture (Tasks 9-12), AI compression (Tasks 5-7),
  model routing (Task 5), hybrid storage with semantic retrieval (already
  in repo, exercised by Task 12), stable IDs + `get_memory_by_id` (Task 4),
  3-layer compact-then-detail (existing `get_context_packet` + new
  `get_memory_by_id`), soft delete (already covered by `archive_memory`).
- **Distributed constraint:** Postgres only — no SQLite anywhere. Multiple
  distiller workers safe via SKIP LOCKED. Hooks talk to the MCP server over
  HTTP, not a local file.
- **Type/name consistency:** `enqueue_observation`, `get_memory_by_id`,
  `select_model`, `ModelChoice`, `DistillerService.distill_once`,
  `StagingRepository.{enqueue,claim_batch,mark_done,mark_failed}`,
  `enqueue` (hook client) — all consistent across tasks.
- **Placeholders:** the migration's `down_revision = "0009_<previous>"` is
  the only intentional placeholder, called out explicitly in Task 1 step 3
  with the exact resolution command (`alembic heads`).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-07-auto-capture-distillation.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task with two-stage review between tasks; fast iteration, clean separation.
2. **Inline Execution** — execute in this session via `superpowers:executing-plans` with batched checkpoints.

Which approach?
