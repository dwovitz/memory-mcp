# memory-mcp PostgreSQL Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the complex PostgreSQL/entities/auth schema with a simplified `memories_v2` + `projects` schema, add 8 new MCP tools + retained `get_context_packet`, add a 13-subcommand CLI, and migrate existing memories — all while preserving benchmark compatibility.

**Architecture:** New `store/` layer (MemoryStore + ProjectStore) over `memories_v2` and `projects` tables using PostgreSQL FTS (GIN + ts_rank) with two-stage retrieval (slim search → selective deep fetch). New `tools/` and `cli/` modules replace the old 12-tool server. Old modules and tables stay in place with `_legacy` suffix until explicitly dropped.

**Tech Stack:** Python 3.12, SQLAlchemy 2, psycopg3, Alembic, FastMCP (mcp package), argparse, pytest with live Docker PostgreSQL.

---

## File Map

**Created:**
- `src/memory_mcp/config.py` ← replaces existing (AppConfig from `~/.memory-mcp/config.json`)
- `src/memory_mcp/detect.py` ← workspace/project root detection + ID generation
- `src/memory_mcp/privacy.py` ← private block stripping + secret detection
- `src/memory_mcp/store/__init__.py`
- `src/memory_mcp/store/projects.py` ← ProjectStore (upsert workspace/project rows)
- `src/memory_mcp/store/memories.py` ← MemoryStore (save/search/get/timeline/checkpoint/prune/update/delete)
- `src/memory_mcp/tools/__init__.py`
- `src/memory_mcp/tools/server.py` ← FastMCP instance + 8 new tool registrations
- `src/memory_mcp/tools/context_packet.py` ← get_context_packet rewired to memories_v2
- `src/memory_mcp/cli/__init__.py`
- `src/memory_mcp/cli/main.py` ← argparse + all 13 subcommands
- `src/memory_mcp/migrate/__init__.py`
- `src/memory_mcp/migrate/legacy.py` ← migrate_from_legacy(), drop_legacy()
- `migrations/versions/0002_memories_v2.py` ← new tables + rename old to _legacy
- `tests/conftest.py` ← shared pytest fixtures (engine, session)
- `tests/test_config.py`
- `tests/test_detect.py`
- `tests/test_privacy.py`
- `tests/test_store.py`
- `tests/test_mcp_tools.py`
- `tests/test_context_packet.py`
- `tests/test_cli.py`
- `tests/test_legacy_migration.py`
- `tests/test_export_import.py`
- `docs/AGENT_MEMORY_POLICY.md`

**Modified:**
- `src/memory_mcp/main.py` ← delegate to CLI
- `pyproject.toml` ← add `memory-mcp-server` script alias
- `src/memory_mcp/db/connection.py` ← use AppConfig instead of DatabaseConfig
- `benchmarks/outline_benchmark_runner.py` ← update seed step tool names

**Preserved (not touched):**
- `src/memory_mcp/auth/`, `audit/`, `retrieval/`, `services/`, `repositories/`, `models/`, `scopes.py`
- `migrations/versions/0001_initial_memory_schema.py`
- `benchmarks/cases.json`, `benchmarks/prompts/`, `benchmarks/results/`

---

## Shared Interfaces (read before writing any task)

```python
# AppConfig (config.py)
@dataclass(frozen=True)
class AppConfig:
    database_url: str
    default_scope: str          # "global"
    max_search_results: int     # 20
    max_summary_chars: int      # 2000
    max_details_chars: int      # 10000
    enable_workspace_detection: bool  # True
    ignored_paths: list[str]
    ignored_tags: list[str]
    log_level: str              # "WARNING"

# SlimMemory (store/memories.py) — returned by search + timeline
@dataclass
class SlimMemory:
    id: str
    title: str
    summary: str
    kind: str
    scope: str
    workspace_id: str | None
    project_id: str | None
    tags: list[str]
    created_at: str   # ISO 8601
    score: float

# FullMemory (store/memories.py) — returned by get
@dataclass
class FullMemory:
    id: str
    title: str
    summary: str
    details: str | None
    kind: str
    scope: str
    workspace_id: str | None
    project_id: str | None
    tags: list[str]
    source: str | None
    confidence: float
    created_at: str
    updated_at: str
    supersedes_id: str | None
    metadata: dict
```

---

## Task 1: Test Infrastructure

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create the test database** (run once, requires Docker PostgreSQL running)

```powershell
docker compose exec postgres psql -U memory_mcp -d postgres -c "CREATE DATABASE memory_mcp_test OWNER memory_mcp;" 2>$null; echo "done"
```

Expected: `CREATE DATABASE` or `already exists` error (both are fine).

- [ ] **Step 2: Write conftest.py**

```python
"""Shared pytest fixtures for memory-mcp tests."""
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


def _test_database_url() -> str:
    url = os.getenv("MEMORY_MCP_TEST_DATABASE_URL")
    if url:
        return url
    base = os.getenv(
        "MEMORY_MCP_DATABASE_URL",
        "postgresql+psycopg://memory_mcp:memory_mcp_password@127.0.0.1:5432/memory_mcp",
    )
    return base.replace("/memory_mcp", "/memory_mcp_test").replace(
        "memory_mcp_test_test", "memory_mcp_test"
    )


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = _test_database_url()
    eng = create_engine(url, pool_pre_ping=True)
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    alembic_command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    conn = engine.connect()
    trans = conn.begin()
    sess = Session(bind=conn)
    yield sess
    sess.close()
    trans.rollback()
    conn.close()
```

- [ ] **Step 3: Run to verify fixture loads (no tests yet)**

```powershell
cd D:\git\ai\memory-mcp; .venv\Scripts\python.exe -m pytest tests/conftest.py --collect-only 2>&1 | head -20
```

Expected: `no tests ran` (fixtures load without error).

- [ ] **Step 4: Commit**

```powershell
git add tests/conftest.py; git commit -m "test: add PostgreSQL session fixture for test suite"
```

---

## Task 2: AppConfig

**Files:**
- Modify: `src/memory_mcp/config.py` (full replacement)
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from __future__ import annotations
import json
from pathlib import Path
import pytest
from memory_mcp.config import AppConfig


def test_defaults_when_no_file(tmp_path):
    cfg = AppConfig.load(config_path=tmp_path / "nonexistent.json")
    assert cfg.default_scope == "global"
    assert cfg.max_search_results == 20
    assert cfg.max_summary_chars == 2000
    assert cfg.max_details_chars == 10000
    assert cfg.enable_workspace_detection is True


def test_loads_from_file(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"max_search_results": 5, "log_level": "DEBUG"}))
    cfg = AppConfig.load(config_path=config_file)
    assert cfg.max_search_results == 5
    assert cfg.log_level == "DEBUG"
    assert cfg.default_scope == "global"  # default still applied


def test_env_var_overrides_file(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"database_url": "postgresql://from-file"}))
    monkeypatch.setenv("MEMORY_MCP_DATABASE_URL", "postgresql://from-env")
    cfg = AppConfig.load(config_path=config_file)
    assert cfg.database_url == "postgresql://from-env"
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py -v 2>&1 | tail -15
```

Expected: `ImportError` or `AttributeError` — AppConfig.load doesn't exist yet.

- [ ] **Step 3: Write config.py**

```python
"""Global configuration loaded from ~/.memory-mcp/config.json and env vars."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


_DEFAULT_CONFIG_PATH = Path.home() / ".memory-mcp" / "config.json"

_DEFAULTS = {
    "database_url": "postgresql+psycopg://memory_mcp:memory_mcp_password@127.0.0.1:5432/memory_mcp",
    "default_scope": "global",
    "max_search_results": 20,
    "max_summary_chars": 2000,
    "max_details_chars": 10000,
    "enable_workspace_detection": True,
    "ignored_paths": [],
    "ignored_tags": [],
    "log_level": "WARNING",
}


@dataclass(frozen=True)
class AppConfig:
    database_url: str
    default_scope: str
    max_search_results: int
    max_summary_chars: int
    max_details_chars: int
    enable_workspace_detection: bool
    ignored_paths: list[str]
    ignored_tags: list[str]
    log_level: str

    @classmethod
    def load(cls, config_path: Path | None = None) -> "AppConfig":
        path = config_path or _DEFAULT_CONFIG_PATH
        data: dict = dict(_DEFAULTS)
        if path.is_file():
            try:
                data.update(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        # env vars win
        if url := os.getenv("MEMORY_MCP_DATABASE_URL"):
            data["database_url"] = url
        if scope := os.getenv("MEMORY_MCP_DEFAULT_SCOPE"):
            data["default_scope"] = scope
        return cls(**{k: data[k] for k in _DEFAULTS})

    def write(self, config_path: Path | None = None) -> None:
        path = config_path or _DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "database_url": self.database_url,
            "default_scope": self.default_scope,
            "max_search_results": self.max_search_results,
            "max_summary_chars": self.max_summary_chars,
            "max_details_chars": self.max_details_chars,
            "enable_workspace_detection": self.enable_workspace_detection,
            "ignored_paths": self.ignored_paths,
            "ignored_tags": self.ignored_tags,
            "log_level": self.log_level,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py -v 2>&1 | tail -15
```

Expected: `3 passed`.

- [ ] **Step 5: Update db/connection.py to accept AppConfig**

Add this function to the bottom of `src/memory_mcp/db/connection.py`:

```python
def engine_from_app_config(config: "AppConfig") -> Engine:
    """Create a SQLAlchemy engine from AppConfig (new path)."""
    from memory_mcp.config import AppConfig as _AppConfig  # noqa: F401
    return create_engine(config.database_url, pool_pre_ping=True)
```

- [ ] **Step 6: Commit**

```powershell
git add src/memory_mcp/config.py src/memory_mcp/db/connection.py tests/test_config.py
git commit -m "feat: add AppConfig loading from ~/.memory-mcp/config.json + env vars"
```

---

## Task 3: Alembic Migration 0002

**Files:**
- Create: `migrations/versions/0002_memories_v2.py`

- [ ] **Step 1: Write the migration**

```python
# migrations/versions/0002_memories_v2.py
"""Add memories_v2 and projects tables; rename legacy tables.

Revision ID: 0002_memories_v2
Revises: 0001_initial_memory_schema
Create Date: 2026-05-03
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0002_memories_v2"
down_revision = "0001_initial_memory_schema"
branch_labels = None
depends_on = None

_LEGACY_RENAMES = [
    ("memories", "memories_legacy"),
    ("memory_tags", "memory_tags_legacy"),
    ("entities", "entities_legacy"),
    ("relationships", "relationships_legacy"),
    ("retrieval_profiles", "retrieval_profiles_legacy"),
    ("context_packets", "context_packets_legacy"),
    ("context_packet_memories", "context_packet_memories_legacy"),
    ("pruning_log", "pruning_log_legacy"),
]


def upgrade() -> None:
    # Rename old tables to _legacy
    for old, new in _LEGACY_RENAMES:
        op.execute(f"ALTER TABLE IF EXISTS {old} RENAME TO {new}")

    # projects (holds both workspaces and projects, kind distinguishes them)
    op.execute("""
        CREATE TABLE projects (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            kind        TEXT NOT NULL DEFAULT 'project',
            root_path   TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata    JSONB NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX projects_kind_idx ON projects (kind)")

    # memories_v2
    op.execute("""
        CREATE TABLE memories_v2 (
            id            TEXT PRIMARY KEY,
            title         TEXT NOT NULL,
            summary       TEXT NOT NULL,
            details       TEXT,
            kind          TEXT NOT NULL DEFAULT 'note',
            scope         TEXT NOT NULL DEFAULT 'global',
            workspace_id  TEXT REFERENCES projects(id),
            project_id    TEXT REFERENCES projects(id),
            tags          JSONB NOT NULL DEFAULT '[]',
            source        TEXT,
            confidence    REAL NOT NULL DEFAULT 1.0,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            supersedes_id TEXT REFERENCES memories_v2(id),
            metadata      JSONB NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("""
        CREATE INDEX memories_v2_fts_idx ON memories_v2
        USING GIN (
            to_tsvector('english',
                title || ' ' || summary || ' ' ||
                coalesce(details, '') || ' ' ||
                coalesce(tags::text, ''))
        )
    """)
    op.execute("CREATE INDEX memories_v2_scope_idx ON memories_v2 (scope, project_id, workspace_id)")
    op.execute("CREATE INDEX memories_v2_kind_idx  ON memories_v2 (kind)")
    op.execute("CREATE INDEX memories_v2_time_idx  ON memories_v2 (created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS memories_v2")
    op.execute("DROP TABLE IF EXISTS projects")
    for old, new in _LEGACY_RENAMES:
        op.execute(f"ALTER TABLE IF EXISTS {new} RENAME TO {old}")
```

- [ ] **Step 2: Apply migration to test database**

```powershell
$env:MEMORY_MCP_TEST_DATABASE_URL = "postgresql+psycopg://memory_mcp:memory_mcp_password@127.0.0.1:5432/memory_mcp_test"
.venv\Scripts\python.exe -c "
from alembic import command
from alembic.config import Config
cfg = Config('alembic.ini')
cfg.set_main_option('sqlalchemy.url', '$env:MEMORY_MCP_TEST_DATABASE_URL')
command.upgrade(cfg, 'head')
print('done')
"
```

Expected: `done` (no errors).

- [ ] **Step 3: Apply migration to main database**

```powershell
alembic upgrade head
```

Expected: `Running upgrade 0001_initial_memory_schema -> 0002_memories_v2, Add memories_v2 and projects tables`.

- [ ] **Step 4: Verify tables exist**

```powershell
docker compose exec postgres psql -U memory_mcp -d memory_mcp -c "\dt memories_v2 projects memories_legacy"
```

Expected: three rows listing `memories_v2`, `projects`, `memories_legacy`.

- [ ] **Step 5: Commit**

```powershell
git add migrations/versions/0002_memories_v2.py
git commit -m "feat: add memories_v2 + projects schema; rename old tables to _legacy"
```

---

## Task 4: Detect (Workspace + Project)

**Files:**
- Create: `src/memory_mcp/detect.py`
- Create: `tests/test_detect.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_detect.py
from __future__ import annotations
from pathlib import Path
import pytest
from memory_mcp.detect import (
    detect_project_root,
    detect_workspace_root,
    make_project_id,
    make_workspace_id,
)


@pytest.fixture
def fake_workspace(tmp_path):
    """tmp_path/workspace/ contains two git repos."""
    ws = tmp_path / "workspace"
    for repo in ("repo-a", "repo-b"):
        (ws / repo / ".git").mkdir(parents=True)
    return ws


def test_detect_project_root(fake_workspace):
    start = fake_workspace / "repo-a" / "src"
    start.mkdir(parents=True)
    root = detect_project_root(start)
    assert root == fake_workspace / "repo-a"


def test_detect_workspace_root(fake_workspace):
    start = fake_workspace / "repo-a" / "src"
    start.mkdir(parents=True)
    ws = detect_workspace_root(start)
    assert ws == fake_workspace


def test_no_workspace_when_single_repo(tmp_path):
    repo = tmp_path / "lone-repo"
    (repo / ".git").mkdir(parents=True)
    start = repo / "src"
    start.mkdir()
    ws = detect_workspace_root(start)
    assert ws is None


def test_project_id_is_deterministic(tmp_path):
    root = tmp_path / "my-repo"
    root.mkdir()
    id1 = make_project_id(root, git_remote=None)
    id2 = make_project_id(root, git_remote=None)
    assert id1 == id2
    assert len(id1) == 16


def test_workspace_id_is_deterministic(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    id1 = make_workspace_id(ws)
    id2 = make_workspace_id(ws)
    assert id1 == id2
    assert len(id1) == 16
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_detect.py -v 2>&1 | tail -15
```

Expected: `ImportError`.

- [ ] **Step 3: Write detect.py**

```python
"""Workspace and project root detection with deterministic ID generation."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


_PROJECT_MARKERS = {
    ".git", "pyproject.toml", "package.json", "Cargo.toml",
    "go.mod", "pom.xml", "build.gradle",
}


def detect_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start looking for a project marker. Returns the marker's directory."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if any((candidate / m).exists() for m in _PROJECT_MARKERS):
            return candidate
    return None


def detect_workspace_root(start: Path | None = None) -> Path | None:
    """Find the highest ancestor that contains multiple child directories with .git."""
    project = detect_project_root(start)
    if project is None:
        return None
    # Walk upward from project's parent; stop when parent no longer has >=2 git children
    workspace: Path | None = None
    for candidate in project.parents:
        git_children = [
            d for d in candidate.iterdir()
            if d.is_dir() and (d / ".git").exists()
        ]
        if len(git_children) >= 2:
            workspace = candidate
        else:
            break
    return workspace


def _hex16(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:16]


def _git_remote(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=root, capture_output=True, text=True, timeout=3,
        )
        url = result.stdout.strip()
        return url if url else None
    except Exception:
        return None


def make_project_id(root_path: Path, git_remote: str | None = None) -> str:
    remote = git_remote or _git_remote(root_path) or ""
    return _hex16(remote + str(root_path.resolve()))


def make_workspace_id(workspace_path: Path) -> str:
    return _hex16(str(workspace_path.resolve()))
```

- [ ] **Step 4: Run tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_detect.py -v 2>&1 | tail -15
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```powershell
git add src/memory_mcp/detect.py tests/test_detect.py
git commit -m "feat: add workspace/project root detection and deterministic ID generation"
```

---

## Task 5: Privacy

**Files:**
- Create: `src/memory_mcp/privacy.py`
- Create: `tests/test_privacy.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_privacy.py
from __future__ import annotations
import pytest
from memory_mcp.privacy import check_for_secrets, strip_private_blocks


@pytest.mark.parametrize("text,expected", [
    ("hello <private>secret</private> world", "hello  world"),
    ("before <PRIVATE>multi\nline</PRIVATE> after", "before  after"),
    ("no private blocks here", "no private blocks here"),
    ("<private>start</private>mid<private>end</private>", "midend"),  # strips both
])
def test_strip_private_blocks(text, expected):
    assert strip_private_blocks(text).strip() == expected.strip()


@pytest.mark.parametrize("text", [
    "OPENAI_API_KEY=sk-abc123def456ghi789jkl012mno345pqr678stu901vwx",
    "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA",
    "password=supersecret123",
    "postgresql://user:p4ssw0rd@host:5432/db",
    "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
])
def test_detects_secrets(text):
    result = check_for_secrets(text)
    assert result is not None, f"Should have detected a secret in: {text!r}"


@pytest.mark.parametrize("text", [
    "This is a normal note about coding",
    "The API endpoint is /api/v1/users",
    "database_url points to localhost",
])
def test_allows_clean_text(text):
    assert check_for_secrets(text) is None
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_privacy.py -v 2>&1 | tail -20
```

Expected: `ImportError`.

- [ ] **Step 3: Write privacy.py**

```python
"""Private block stripping and secret pattern detection."""
from __future__ import annotations

import re

_PRIVATE_RE = re.compile(r"<private>.*?</private>", re.IGNORECASE | re.DOTALL)

_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("api_key", re.compile(r"(?i)(api[_-]?key|secret[_-]?key)\s*[=:]\s*\S{16,}")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+")),
    ("private_key_header", re.compile(r"-----BEGIN\s+[A-Z ]*PRIVATE KEY-----")),
    ("aws_secret", re.compile(r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*\S{20,}")),
    ("password_assignment", re.compile(r"(?i)password\s*[=:]\s*\S{6,}")),
    ("connection_string_with_creds", re.compile(
        r"(?i)(postgresql|mysql|mongodb|redis)://[^:@\s]+:[^@\s]+@"
    )),
    ("dotenv_secret", re.compile(
        r"(?im)^(TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL|API_KEY)[_A-Z]*\s*=\s*\S{8,}"
    )),
]


def strip_private_blocks(text: str) -> str:
    """Remove all <private>...</private> blocks from text."""
    return _PRIVATE_RE.sub("", text)


def check_for_secrets(text: str) -> str | None:
    """Return the pattern name if text looks like it contains a secret, else None."""
    for name, pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return name
    return None
```

- [ ] **Step 4: Run tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_privacy.py -v 2>&1 | tail -20
```

Expected: all passed.

- [ ] **Step 5: Commit**

```powershell
git add src/memory_mcp/privacy.py tests/test_privacy.py
git commit -m "feat: add private block stripping and secret detection"
```

---

## Task 6: ProjectStore

**Files:**
- Create: `src/memory_mcp/store/__init__.py`
- Create: `src/memory_mcp/store/projects.py`
- Create: `tests/test_store.py` (partial — ProjectStore tests)

- [ ] **Step 1: Write failing tests (add to test_store.py)**

```python
# tests/test_store.py
from __future__ import annotations
import pytest
from memory_mcp.store.projects import ProjectStore


def test_get_or_create_project(session):
    store = ProjectStore(session)
    pid = store.get_or_create(name="my-repo", kind="project", root_path="/home/user/my-repo")
    assert len(pid) == 16
    # idempotent
    pid2 = store.get_or_create(name="my-repo", kind="project", root_path="/home/user/my-repo")
    assert pid == pid2


def test_get_or_create_workspace(session):
    store = ProjectStore(session)
    wid = store.get_or_create(name="ai", kind="workspace", root_path="/home/user/ai")
    assert len(wid) == 16


def test_different_roots_different_ids(session):
    store = ProjectStore(session)
    id1 = store.get_or_create(name="repo-a", kind="project", root_path="/ws/repo-a")
    id2 = store.get_or_create(name="repo-b", kind="project", root_path="/ws/repo-b")
    assert id1 != id2
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_store.py -v 2>&1 | tail -15
```

Expected: `ImportError` or `fixture 'session' not found` (both fine at this stage).

- [ ] **Step 3: Create store/__init__.py**

```python
"""Store layer for memories_v2 and projects tables."""
```

- [ ] **Step 4: Write store/projects.py**

```python
"""ProjectStore: upsert workspaces and projects into the projects table."""
from __future__ import annotations

import hashlib
from sqlalchemy import text
from sqlalchemy.orm import Session


def _make_id(root_path: str) -> str:
    return hashlib.sha256(root_path.encode()).hexdigest()[:16]


class ProjectStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, *, name: str, kind: str, root_path: str | None = None) -> str:
        """Return the project ID, inserting a new row only if root_path is new."""
        key = root_path or name
        pid = _make_id(key)
        self.session.execute(
            text("""
                INSERT INTO projects (id, name, kind, root_path)
                VALUES (:id, :name, :kind, :root_path)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    updated_at = now()
            """),
            {"id": pid, "name": name, "kind": kind, "root_path": root_path},
        )
        return pid
```

- [ ] **Step 5: Run tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_store.py -v 2>&1 | tail -15
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```powershell
git add src/memory_mcp/store/ tests/test_store.py
git commit -m "feat: add ProjectStore for workspace/project upsert"
```

---

## Task 7: MemoryStore — CRUD + Search

**Files:**
- Create: `src/memory_mcp/store/memories.py`
- Extend: `tests/test_store.py`

- [ ] **Step 1: Write failing tests (append to test_store.py)**

```python
# append to tests/test_store.py
from memory_mcp.config import AppConfig
from memory_mcp.store.memories import FullMemory, MemoryStore, SlimMemory


def _store(session) -> MemoryStore:
    cfg = AppConfig.load()
    return MemoryStore(session, cfg)


def test_save_and_get(session):
    store = _store(session)
    mid, updated = store.save(title="Test memory", summary="A test summary", scope="global")
    assert len(mid) == 32
    assert updated is False
    results = store.get([mid])
    assert len(results) == 1
    assert results[0].title == "Test memory"
    assert results[0].summary == "A test summary"
    assert results[0].scope == "global"


def test_search_returns_slim(session):
    store = _store(session)
    store.save(title="Python decorator patterns", summary="Use functools.wraps in decorators", scope="global")
    results = store.search(query="python decorator")
    assert len(results) >= 1
    assert isinstance(results[0], SlimMemory)
    assert not hasattr(results[0], "details") or results[0].__class__.__name__ == "SlimMemory"


def test_get_returns_full(session):
    store = _store(session)
    mid, _ = store.save(
        title="Full memory", summary="Short summary",
        details="Long details here", scope="global"
    )
    results = store.get([mid])
    assert isinstance(results[0], FullMemory)
    assert results[0].details == "Long details here"


def test_dedup_updates_existing(session):
    store = _store(session)
    mid1, updated1 = store.save(title="SQLAlchemy session pattern", summary="Use session_scope context manager", scope="global", kind="preference")
    mid2, updated2 = store.save(title="SQLAlchemy session pattern", summary="Updated: session_scope is preferred", scope="global", kind="preference")
    assert updated2 is True
    assert mid1 == mid2


def test_timeline_ordering(session):
    store = _store(session)
    store.save(title="First", summary="first memory", scope="global")
    store.save(title="Second", summary="second memory", scope="global")
    timeline = store.timeline(limit=10)
    titles = [m.title for m in timeline]
    assert titles.index("Second") < titles.index("First")


def test_update(session):
    store = _store(session)
    mid, _ = store.save(title="Original", summary="original summary", scope="global")
    store.update(mid, summary="updated summary")
    full = store.get([mid])
    assert full[0].summary == "updated summary"


def test_delete(session):
    store = _store(session)
    mid, _ = store.save(title="To delete", summary="will be gone", scope="global")
    deleted = store.delete([mid])
    assert mid in deleted
    assert store.get([mid]) == []
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_store.py -k "test_save" -v 2>&1 | tail -10
```

Expected: `ImportError` for MemoryStore.

- [ ] **Step 3: Write store/memories.py**

```python
"""MemoryStore: CRUD + FTS search on memories_v2."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from memory_mcp.config import AppConfig
from memory_mcp.privacy import check_for_secrets, strip_private_blocks


VALID_KINDS = {
    "preference", "decision", "checkpoint", "architecture",
    "bug", "command", "environment", "workflow", "note",
}
VALID_SCOPES = {"global", "workspace", "project"}
DEDUP_SCORE_THRESHOLD = 0.3  # ts_rank threshold for considering a save a duplicate


@dataclass
class SlimMemory:
    id: str
    title: str
    summary: str
    kind: str
    scope: str
    workspace_id: str | None
    project_id: str | None
    tags: list[str]
    created_at: str
    score: float


@dataclass
class FullMemory:
    id: str
    title: str
    summary: str
    details: str | None
    kind: str
    scope: str
    workspace_id: str | None
    project_id: str | None
    tags: list[str]
    source: str | None
    confidence: float
    created_at: str
    updated_at: str
    supersedes_id: str | None
    metadata: dict


def _clean(text_val: str, field: str) -> str:
    stripped = strip_private_blocks(text_val)
    secret = check_for_secrets(stripped)
    if secret:
        raise ValueError(f"Refusing to save: detected {secret} pattern in {field}")
    return stripped


def _truncate(text_val: str | None, limit: int) -> str | None:
    if text_val is None:
        return None
    if len(text_val) > limit:
        return text_val[:limit] + "…[truncated]"
    return text_val


class MemoryStore:
    def __init__(self, session: Session, config: AppConfig) -> None:
        self.session = session
        self.config = config

    def save(
        self, *, title: str, summary: str, details: str | None = None,
        kind: str = "note", scope: str = "global",
        workspace_id: str | None = None, project_id: str | None = None,
        tags: list[str] | None = None, source: str | None = None,
        confidence: float = 1.0,
    ) -> tuple[str, bool]:
        """Save a memory. Returns (id, was_updated). Deduplicates by FTS on title."""
        title = _clean(title, "title")
        summary = _clean(summary, "summary")
        if details:
            details = _clean(details, "details")
        kind = kind if kind in VALID_KINDS else "note"
        scope = scope if scope in VALID_SCOPES else "global"
        summary = _truncate(summary, self.config.max_summary_chars) or summary
        details = _truncate(details, self.config.max_details_chars)
        tags_json = json.dumps(tags or [])

        # Check for duplicate by FTS on title within same scope+kind
        existing = self._find_duplicate(title, scope, kind, workspace_id, project_id)
        if existing:
            self.session.execute(
                text("""
                    UPDATE memories_v2 SET
                        title = :title, summary = :summary, details = :details,
                        tags = :tags::jsonb, confidence = :confidence,
                        updated_at = now()
                    WHERE id = :id
                """),
                {"id": existing, "title": title, "summary": summary,
                 "details": details, "tags": tags_json, "confidence": confidence},
            )
            return existing, True

        mid = uuid.uuid4().hex
        self.session.execute(
            text("""
                INSERT INTO memories_v2
                    (id, title, summary, details, kind, scope,
                     workspace_id, project_id, tags, source, confidence)
                VALUES
                    (:id, :title, :summary, :details, :kind, :scope,
                     :workspace_id, :project_id, :tags::jsonb, :source, :confidence)
            """),
            {
                "id": mid, "title": title, "summary": summary, "details": details,
                "kind": kind, "scope": scope, "workspace_id": workspace_id,
                "project_id": project_id, "tags": tags_json,
                "source": source, "confidence": confidence,
            },
        )
        return mid, False

    def _find_duplicate(
        self, title: str, scope: str, kind: str,
        workspace_id: str | None, project_id: str | None,
    ) -> str | None:
        """Return ID of an existing memory that's a close title match, or None."""
        row = self.session.execute(
            text("""
                SELECT id,
                    ts_rank(
                        to_tsvector('english', title),
                        plainto_tsquery('english', :title)
                    ) AS score
                FROM memories_v2
                WHERE to_tsvector('english', title) @@ plainto_tsquery('english', :title)
                  AND scope = :scope AND kind = :kind
                  AND (:workspace_id IS NULL OR workspace_id = :workspace_id)
                  AND (:project_id IS NULL OR project_id = :project_id)
                ORDER BY score DESC
                LIMIT 1
            """),
            {"title": title, "scope": scope, "kind": kind,
             "workspace_id": workspace_id, "project_id": project_id},
        ).fetchone()
        if row and row.score >= DEDUP_SCORE_THRESHOLD:
            return row.id
        return None

    def search(
        self, *, query: str, scopes: list[str] | None = None,
        workspace_id: str | None = None, project_id: str | None = None,
        tags: list[str] | None = None, kind: str | None = None,
        limit: int | None = None,
    ) -> list[SlimMemory]:
        """Stage 1 slim search. Returns compact rows, no details."""
        effective_limit = min(limit or self.config.max_search_results, self.config.max_search_results)
        rows = self.session.execute(
            text("""
                SELECT id, title, summary, kind, scope, workspace_id, project_id,
                       tags, created_at,
                       ts_rank(
                           to_tsvector('english',
                               title || ' ' || summary || ' ' ||
                               coalesce(details, '') || ' ' ||
                               coalesce(tags::text, '')),
                           plainto_tsquery('english', :query)
                       ) * CASE scope
                           WHEN 'project'   THEN 1.0
                           WHEN 'workspace' THEN 0.8
                           ELSE                  0.6
                       END AS score
                FROM memories_v2
                WHERE to_tsvector('english',
                          title || ' ' || summary || ' ' ||
                          coalesce(details, '') || ' ' ||
                          coalesce(tags::text, ''))
                      @@ plainto_tsquery('english', :query)
                  AND (:scopes_null OR scope = ANY(:scopes))
                  AND (:workspace_id IS NULL OR workspace_id = :workspace_id)
                  AND (:project_id IS NULL OR project_id = :project_id)
                  AND (:kind IS NULL OR kind = :kind)
                ORDER BY score DESC, created_at DESC
                LIMIT :limit
            """),
            {
                "query": query,
                "scopes_null": scopes is None,
                "scopes": scopes or [],
                "workspace_id": workspace_id,
                "project_id": project_id,
                "kind": kind,
                "limit": effective_limit,
            },
        ).fetchall()
        return [
            SlimMemory(
                id=r.id, title=r.title, summary=r.summary, kind=r.kind,
                scope=r.scope, workspace_id=r.workspace_id, project_id=r.project_id,
                tags=r.tags or [], created_at=r.created_at.isoformat(), score=float(r.score),
            )
            for r in rows
        ]

    def get(self, ids: list[str]) -> list[FullMemory]:
        """Stage 2 deep fetch. Returns full records for requested IDs only."""
        if not ids:
            return []
        rows = self.session.execute(
            text("SELECT * FROM memories_v2 WHERE id = ANY(:ids)"),
            {"ids": ids},
        ).fetchall()
        return [
            FullMemory(
                id=r.id, title=r.title, summary=r.summary, details=r.details,
                kind=r.kind, scope=r.scope, workspace_id=r.workspace_id,
                project_id=r.project_id, tags=r.tags or [],
                source=r.source, confidence=float(r.confidence),
                created_at=r.created_at.isoformat(), updated_at=r.updated_at.isoformat(),
                supersedes_id=r.supersedes_id, metadata=r.metadata or {},
            )
            for r in rows
        ]

    def timeline(
        self, *, scopes: list[str] | None = None,
        workspace_id: str | None = None, project_id: str | None = None,
        since: str | None = None, limit: int = 20, kind: str | None = None,
    ) -> list[SlimMemory]:
        rows = self.session.execute(
            text("""
                SELECT id, title, summary, kind, scope, workspace_id, project_id,
                       tags, created_at, 1.0 AS score
                FROM memories_v2
                WHERE (:scopes_null OR scope = ANY(:scopes))
                  AND (:workspace_id IS NULL OR workspace_id = :workspace_id)
                  AND (:project_id IS NULL OR project_id = :project_id)
                  AND (:since IS NULL OR created_at > :since::timestamptz)
                  AND (:kind IS NULL OR kind = :kind)
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {
                "scopes_null": scopes is None,
                "scopes": scopes or [],
                "workspace_id": workspace_id,
                "project_id": project_id,
                "since": since,
                "kind": kind,
                "limit": limit,
            },
        ).fetchall()
        return [
            SlimMemory(
                id=r.id, title=r.title, summary=r.summary, kind=r.kind,
                scope=r.scope, workspace_id=r.workspace_id, project_id=r.project_id,
                tags=r.tags or [], created_at=r.created_at.isoformat(), score=float(r.score),
            )
            for r in rows
        ]

    def update(
        self, id: str, *, title: str | None = None, summary: str | None = None,
        details: str | None = None, tags: list[str] | None = None,
        kind: str | None = None, confidence: float | None = None,
    ) -> str:
        sets, params = ["updated_at = now()"], {"id": id}
        if title is not None:
            sets.append("title = :title"); params["title"] = _clean(title, "title")
        if summary is not None:
            sets.append("summary = :summary"); params["summary"] = _clean(summary, "summary")
        if details is not None:
            sets.append("details = :details"); params["details"] = _clean(details, "details")
        if tags is not None:
            sets.append("tags = :tags::jsonb"); params["tags"] = json.dumps(tags)
        if kind is not None:
            sets.append("kind = :kind"); params["kind"] = kind
        if confidence is not None:
            sets.append("confidence = :confidence"); params["confidence"] = confidence
        self.session.execute(
            text(f"UPDATE memories_v2 SET {', '.join(sets)} WHERE id = :id"), params
        )
        return id

    def delete(self, ids: list[str]) -> list[str]:
        if not ids:
            return []
        self.session.execute(
            text("DELETE FROM memories_v2 WHERE id = ANY(:ids)"), {"ids": ids}
        )
        return ids

    def checkpoint(
        self, *, task: str, state: str, next_steps: list[str] | None = None,
        blockers: list[str] | None = None, files_changed: list[str] | None = None,
        commands_run: list[str] | None = None, scope: str = "project",
        workspace_id: str | None = None, project_id: str | None = None,
    ) -> tuple[str, str]:
        """Save a resumable checkpoint. Returns (checkpoint_id, resume_summary)."""
        lines = [f"**Task:** {task}", f"**State:** {state}"]
        if next_steps:
            lines.append("**Next steps:** " + "; ".join(next_steps))
        if blockers:
            lines.append("**Blockers:** " + "; ".join(blockers))
        if files_changed:
            lines.append("**Files:** " + ", ".join(files_changed))
        if commands_run:
            lines.append("**Commands:** " + "; ".join(commands_run))
        resume_summary = "\n".join(lines)
        details = json.dumps({
            "task": task, "state": state,
            "next_steps": next_steps or [],
            "blockers": blockers or [],
            "files_changed": files_changed or [],
            "commands_run": commands_run or [],
        })
        mid, _ = self.save(
            title=f"Checkpoint: {task[:80]}",
            summary=state[:self.config.max_summary_chars],
            details=details,
            kind="checkpoint",
            scope=scope,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        return mid, resume_summary

    def prune(
        self, *, dry_run: bool = True, older_than_days: int | None = None,
        scope: str | None = None, workspace_id: str | None = None,
        project_id: str | None = None, tags: list[str] | None = None,
        kind: str | None = None,
    ) -> dict:
        """Identify stale/duplicate memories. Deletes only when dry_run=False."""
        conditions = ["1=1"]
        params: dict = {}
        if older_than_days:
            conditions.append("created_at < now() - interval ':days days'")
            params["days"] = older_than_days
        if scope:
            conditions.append("scope = :scope"); params["scope"] = scope
        if workspace_id:
            conditions.append("workspace_id = :workspace_id"); params["workspace_id"] = workspace_id
        if project_id:
            conditions.append("project_id = :project_id"); params["project_id"] = project_id
        if kind:
            conditions.append("kind = :kind"); params["kind"] = kind

        where = " AND ".join(conditions)
        candidates = self.session.execute(
            text(f"SELECT id, title, kind, scope, created_at FROM memories_v2 WHERE {where}"),
            params,
        ).fetchall()

        stale_ids = [r.id for r in candidates if older_than_days]
        report = {
            "dry_run": dry_run,
            "would_delete": len(stale_ids),
            "candidates": [
                {"id": r.id, "title": r.title, "kind": r.kind, "scope": r.scope}
                for r in candidates[:50]
            ],
        }
        if not dry_run and stale_ids:
            self.delete(stale_ids)
            report["deleted"] = len(stale_ids)
        return report
```

- [ ] **Step 4: Run all store tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_store.py -v 2>&1 | tail -25
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/memory_mcp/store/memories.py tests/test_store.py
git commit -m "feat: add MemoryStore with FTS search, dedup, checkpoint, prune, CRUD"
```

---

## Task 8: MCP Tools (8 new tools)

**Files:**
- Create: `src/memory_mcp/tools/__init__.py`
- Create: `src/memory_mcp/tools/server.py`
- Create: `tests/test_mcp_tools.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_mcp_tools.py
from __future__ import annotations
import pytest
from mcp.server.fastmcp import FastMCP
from memory_mcp.tools.server import mcp


def test_mcp_instance():
    assert isinstance(mcp, FastMCP)


def test_required_tools_registered():
    names = {t.name for t in mcp._tool_manager.list_tools()}
    required = {
        "memory_search", "memory_get", "memory_save", "memory_timeline",
        "memory_checkpoint", "memory_prune", "memory_update", "memory_delete",
    }
    assert required.issubset(names), f"Missing tools: {required - names}"
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_mcp_tools.py -v 2>&1 | tail -10
```

Expected: `ImportError`.

- [ ] **Step 3: Create tools/__init__.py**

```python
"""MCP tool definitions."""
```

- [ ] **Step 4: Write tools/server.py**

```python
"""FastMCP server with 8 new memory tools."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from memory_mcp.config import AppConfig
from memory_mcp.db.connection import engine_from_app_config
from memory_mcp.store.memories import MemoryStore
from memory_mcp.store.projects import ProjectStore
from sqlalchemy.orm import Session

mcp = FastMCP("memory-mcp")
_config: AppConfig | None = None


def _get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig.load()
    return _config


def _store(session: Session) -> MemoryStore:
    return MemoryStore(session, _get_config())


@mcp.tool()
def memory_search(
    query: str,
    scope: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    tags: list[str] | None = None,
    kind: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Search memories (compact results — no details). Use memory_get for full records."""
    cfg = _get_config()
    engine = engine_from_app_config(cfg)
    with Session(engine) as session:
        results = _store(session).search(
            query=query,
            scopes=[scope] if scope else None,
            workspace_id=workspace_id,
            project_id=project_id,
            tags=tags,
            kind=kind,
            limit=limit,
        )
    return [
        {"id": r.id, "title": r.title, "summary": r.summary, "kind": r.kind,
         "scope": r.scope, "workspace_id": r.workspace_id, "project_id": r.project_id,
         "tags": r.tags, "created_at": r.created_at, "score": r.score}
        for r in results
    ]


@mcp.tool()
def memory_get(ids: list[str]) -> list[dict]:
    """Fetch full memory records by ID. Call after memory_search to get details."""
    cfg = _get_config()
    engine = engine_from_app_config(cfg)
    with Session(engine) as session:
        results = _store(session).get(ids)
    return [
        {"id": r.id, "title": r.title, "summary": r.summary, "details": r.details,
         "kind": r.kind, "scope": r.scope, "workspace_id": r.workspace_id,
         "project_id": r.project_id, "tags": r.tags, "source": r.source,
         "confidence": r.confidence, "created_at": r.created_at,
         "updated_at": r.updated_at, "supersedes_id": r.supersedes_id,
         "metadata": r.metadata}
        for r in results
    ]


@mcp.tool()
def memory_save(
    title: str,
    summary: str,
    details: str | None = None,
    kind: str = "note",
    scope: str = "global",
    workspace_id: str | None = None,
    project_id: str | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
    confidence: float = 1.0,
) -> dict:
    """Save a memory. Deduplicates against similar existing memories in the same scope+kind."""
    cfg = _get_config()
    engine = engine_from_app_config(cfg)
    with Session(engine) as session:
        mid, updated = _store(session).save(
            title=title, summary=summary, details=details, kind=kind,
            scope=scope, workspace_id=workspace_id, project_id=project_id,
            tags=tags, source=source, confidence=confidence,
        )
        session.commit()
    return {"id": mid, "updated": updated}


@mcp.tool()
def memory_timeline(
    scope: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    since: str | None = None,
    limit: int = 20,
    kind: str | None = None,
) -> list[dict]:
    """Recent memories in chronological order (compact)."""
    cfg = _get_config()
    engine = engine_from_app_config(cfg)
    with Session(engine) as session:
        results = _store(session).timeline(
            scopes=[scope] if scope else None,
            workspace_id=workspace_id, project_id=project_id,
            since=since, limit=limit, kind=kind,
        )
    return [
        {"id": r.id, "title": r.title, "summary": r.summary, "kind": r.kind,
         "scope": r.scope, "created_at": r.created_at}
        for r in results
    ]


@mcp.tool()
def memory_checkpoint(
    task: str,
    state: str,
    next_steps: list[str] | None = None,
    blockers: list[str] | None = None,
    files_changed: list[str] | None = None,
    commands_run: list[str] | None = None,
    scope: str = "project",
    workspace_id: str | None = None,
    project_id: str | None = None,
) -> dict:
    """Save a resumable work checkpoint optimised for session resume after reset."""
    cfg = _get_config()
    engine = engine_from_app_config(cfg)
    with Session(engine) as session:
        mid, resume = _store(session).checkpoint(
            task=task, state=state, next_steps=next_steps, blockers=blockers,
            files_changed=files_changed, commands_run=commands_run,
            scope=scope, workspace_id=workspace_id, project_id=project_id,
        )
        session.commit()
    return {"id": mid, "resume_summary": resume}


@mcp.tool()
def memory_prune(
    dry_run: bool = True,
    older_than_days: int | None = None,
    scope: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    tags: list[str] | None = None,
    kind: str | None = None,
) -> dict:
    """Identify stale or duplicate memories. dry_run=True by default — inspect before deleting."""
    cfg = _get_config()
    engine = engine_from_app_config(cfg)
    with Session(engine) as session:
        result = _store(session).prune(
            dry_run=dry_run, older_than_days=older_than_days, scope=scope,
            workspace_id=workspace_id, project_id=project_id, tags=tags, kind=kind,
        )
        if not dry_run:
            session.commit()
    return result


@mcp.tool()
def memory_update(
    id: str,
    title: str | None = None,
    summary: str | None = None,
    details: str | None = None,
    tags: list[str] | None = None,
    kind: str | None = None,
    confidence: float | None = None,
) -> dict:
    """Update a specific memory record. Preserves created_at."""
    cfg = _get_config()
    engine = engine_from_app_config(cfg)
    with Session(engine) as session:
        _store(session).update(
            id, title=title, summary=summary, details=details,
            tags=tags, kind=kind, confidence=confidence,
        )
        session.commit()
    return {"id": id}


@mcp.tool()
def memory_delete(ids: list[str]) -> dict:
    """Delete explicitly listed memory IDs."""
    cfg = _get_config()
    engine = engine_from_app_config(cfg)
    with Session(engine) as session:
        deleted = _store(session).delete(ids)
        session.commit()
    return {"deleted": deleted}


def run_stdio() -> None:
    mcp.run(transport="stdio")


def run_http(port: int = 8080) -> None:
    mcp.run(transport="sse", port=port)
```

- [ ] **Step 5: Add engine_from_app_config to db/connection.py** (if not already done in Task 2 Step 5 — verify it exists)

```powershell
.venv\Scripts\python.exe -c "from memory_mcp.db.connection import engine_from_app_config; print('ok')"
```

Expected: `ok`. If not, add the function as shown in Task 2 Step 5.

- [ ] **Step 6: Run tool tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_mcp_tools.py -v 2>&1 | tail -15
```

Expected: `2 passed`.

- [ ] **Step 7: Commit**

```powershell
git add src/memory_mcp/tools/ tests/test_mcp_tools.py
git commit -m "feat: add 8 new MCP tools (memory_search/get/save/timeline/checkpoint/prune/update/delete)"
```

---

## Task 9: get_context_packet Rewrite

**Files:**
- Create: `src/memory_mcp/tools/context_packet.py`
- Create: `tests/test_context_packet.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_context_packet.py
from __future__ import annotations
import pytest
from memory_mcp.config import AppConfig
from memory_mcp.store.memories import MemoryStore
from memory_mcp.tools.context_packet import synthesize_packet
from sqlalchemy.orm import Session


def test_packet_has_required_fields(session):
    cfg = AppConfig.load()
    store = MemoryStore(session, cfg)
    store.save(title="FastMCP usage", summary="Use @mcp.tool() decorator", scope="global", kind="architecture")
    session.flush()

    packet = synthesize_packet(
        session=session,
        config=cfg,
        request="How do I register MCP tools?",
        workspace_id=None,
        project_id=None,
        component=None,
        max_memories=5,
        max_tokens=500,
    )
    assert "preferences" in packet
    assert "facts" in packet
    assert "context_quality" in packet
    assert "suggested_next_action" in packet
    assert "source_read_policy" in packet
    assert "source_read_budget_tokens" in packet


def test_packet_prefers_project_scope(session):
    cfg = AppConfig.load()
    store = MemoryStore(session, cfg)
    store.save(title="Global rule", summary="global preference", scope="global", kind="preference")
    proj_id = "testproj01234567"
    store.save(title="Project auth pattern", summary="project uses sessions", scope="project",
               project_id=proj_id, kind="architecture")
    session.flush()

    packet = synthesize_packet(
        session=session, config=cfg,
        request="auth pattern",
        workspace_id=None, project_id=proj_id, component=None,
        max_memories=10, max_tokens=2000,
    )
    titles = [m["title"] for m in packet.get("facts", [])]
    assert any("Project auth" in t for t in titles), f"Project memory not in packet: {titles}"
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_context_packet.py -v 2>&1 | tail -10
```

Expected: `ImportError`.

- [ ] **Step 3: Write tools/context_packet.py**

```python
"""get_context_packet rewired to memories_v2 with two-stage retrieval."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from memory_mcp.config import AppConfig
from memory_mcp.db.connection import engine_from_app_config
from memory_mcp.store.memories import MemoryStore
from memory_mcp.tools.server import mcp

_PREFERENCE_KINDS = {"preference", "workflow", "environment"}
_FACT_KINDS = {"architecture", "decision", "bug", "command", "note"}
_CHECKPOINT_KINDS = {"checkpoint"}

# Source read policy thresholds (token counts)
_VERIFY_THRESHOLD = 400
_IMPLEMENTATION_THRESHOLD = 800


def synthesize_packet(
    *,
    session: Session,
    config: AppConfig,
    request: str,
    workspace_id: str | None,
    project_id: str | None,
    component: str | None,
    max_memories: int,
    max_tokens: int,
) -> dict:
    """Run two-stage retrieval and return a structured context packet."""
    store = MemoryStore(session, config)

    # Augment query with component hint
    query = f"{request} {component}" if component else request

    # Stage 1: slim search across all applicable scopes
    slim = store.search(
        query=query,
        workspace_id=workspace_id,
        project_id=project_id,
        limit=max_memories * 3,
    )

    if not slim:
        return _empty_packet(request)

    # Stage 2: deep fetch top results
    top_ids = [r.id for r in slim[:max_memories]]
    full = store.get(top_ids)
    full_by_id = {r.id: r for r in full}

    preferences, facts, checkpoints = [], [], []
    token_estimate = 0

    for slim_r in slim[:max_memories]:
        full_r = full_by_id.get(slim_r.id)
        if full_r is None:
            continue
        entry = {
            "id": full_r.id,
            "title": full_r.title,
            "summary": full_r.summary,
            "kind": full_r.kind,
            "scope": full_r.scope,
            "confidence": full_r.confidence,
        }
        token_estimate += len(full_r.summary) // 4
        if full_r.kind in _PREFERENCE_KINDS:
            preferences.append(entry)
        elif full_r.kind in _CHECKPOINT_KINDS:
            checkpoints.append(entry)
        else:
            facts.append(entry)

    has_project_memory = any(
        r.scope == "project" and r.project_id == project_id
        for r in slim[:max_memories]
        if project_id
    )
    context_quality = "strong" if has_project_memory else ("moderate" if slim else "weak")

    if token_estimate < _VERIFY_THRESHOLD:
        policy, budget = "mark_weak_context", 0
    elif token_estimate < _IMPLEMENTATION_THRESHOLD:
        policy, budget = "verify_narrowly", 2000
    else:
        policy, budget = "answer_from_packet", 0

    return {
        "request": request,
        "preferences": preferences,
        "facts": facts,
        "checkpoints": checkpoints,
        "context_quality": context_quality,
        "suggested_next_action": (
            "Answer from memory packet." if context_quality == "strong"
            else "Search memory then verify narrowly in source." if context_quality == "moderate"
            else "Memory context is weak — inspect source before answering."
        ),
        "source_read_policy": policy,
        "source_read_budget_tokens": budget,
        "matched_memories": len(slim),
        "token_estimate": token_estimate,
    }


def _empty_packet(request: str) -> dict:
    return {
        "request": request,
        "preferences": [], "facts": [], "checkpoints": [],
        "context_quality": "weak",
        "suggested_next_action": "No memory found — inspect source.",
        "source_read_policy": "mark_weak_context",
        "source_read_budget_tokens": 0,
        "matched_memories": 0,
        "token_estimate": 0,
    }


@mcp.tool()
def get_context_packet(
    request: str,
    workspace: str | None = None,
    project: str | None = None,
    component: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,
    max_memories: int = 8,
    max_tokens: int = 1200,
) -> dict:
    """Synthesise a compact context packet for an agent before coding work.
    
    Two-stage: slim FTS search → deep fetch of top results → structured packet.
    Returns preferences, facts, checkpoints, context_quality, source_read_policy.
    """
    cfg = AppConfig.load()
    engine = engine_from_app_config(cfg)

    # Accept either human-readable names or resolved IDs
    resolved_workspace_id = workspace_id
    resolved_project_id = project_id

    with Session(engine) as session:
        if workspace and not workspace_id:
            from memory_mcp.store.projects import ProjectStore
            ps = ProjectStore(session)
            resolved_workspace_id = ps.get_or_create(name=workspace, kind="workspace")
        if project and not project_id:
            from memory_mcp.store.projects import ProjectStore
            ps = ProjectStore(session)
            resolved_project_id = ps.get_or_create(name=project, kind="project")

        packet = synthesize_packet(
            session=session, config=cfg, request=request,
            workspace_id=resolved_workspace_id, project_id=resolved_project_id,
            component=component, max_memories=max_memories, max_tokens=max_tokens,
        )
    return packet
```

- [ ] **Step 4: Register context_packet tool by importing in tools/__init__.py**

```python
# src/memory_mcp/tools/__init__.py
"""MCP tool definitions."""
from memory_mcp.tools import context_packet  # noqa: F401 — registers get_context_packet
```

- [ ] **Step 5: Run tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_context_packet.py tests/test_mcp_tools.py -v 2>&1 | tail -20
```

Expected: all pass. `test_required_tools_registered` should now also see `get_context_packet` registered.

- [ ] **Step 6: Commit**

```powershell
git add src/memory_mcp/tools/context_packet.py src/memory_mcp/tools/__init__.py tests/test_context_packet.py
git commit -m "feat: rewrite get_context_packet with two-stage retrieval on memories_v2"
```

---

## Task 10: CLI

**Files:**
- Create: `src/memory_mcp/cli/__init__.py`
- Create: `src/memory_mcp/cli/main.py`
- Modify: `src/memory_mcp/main.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write smoke tests**

```python
# tests/test_cli.py
from __future__ import annotations
import subprocess
import sys


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "memory_mcp.cli.main", *args],
        capture_output=True, text=True,
    )


def test_doctor_exits_zero():
    result = _run("doctor")
    assert result.returncode == 0, result.stderr


def test_search_runs():
    result = _run("search", "python")
    assert result.returncode == 0, result.stderr


def test_timeline_runs():
    result = _run("timeline")
    assert result.returncode == 0, result.stderr


def test_unknown_subcommand_exits_nonzero():
    result = _run("notacommand")
    assert result.returncode != 0
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_cli.py -v 2>&1 | tail -15
```

Expected: errors (module not found or non-zero exit).

- [ ] **Step 3: Create cli/__init__.py**

```python
"""CLI entry point for memory-mcp."""
```

- [ ] **Step 4: Write cli/main.py**

```python
"""CLI for memory-mcp: 13 subcommands via argparse."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from memory_mcp.config import AppConfig
from memory_mcp.db.connection import engine_from_app_config
from memory_mcp.store.memories import MemoryStore
from memory_mcp.store.projects import ProjectStore
from sqlalchemy.orm import Session


def _config() -> AppConfig:
    return AppConfig.load()


def _session(cfg: AppConfig) -> Session:
    return Session(engine_from_app_config(cfg))


# ── subcommand handlers ────────────────────────────────────────────────────────

def cmd_init(args: argparse.Namespace) -> int:
    home = Path.home() / ".memory-mcp"
    home.mkdir(parents=True, exist_ok=True)
    cfg_path = home / "config.json"
    if not cfg_path.exists():
        AppConfig.load().write(cfg_path)
        print(f"Created {cfg_path}")
    else:
        print(f"Config already exists at {cfg_path}")
    # Apply migrations
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig
    cfg = _config()
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", cfg.database_url)
    alembic_command.upgrade(alembic_cfg, "head")
    print("Migrations applied.")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = _config()
    errors = []
    try:
        from sqlalchemy import text
        with _session(cfg) as sess:
            sess.execute(text("SELECT 1"))
        print("✓ Database connection OK")
    except Exception as e:
        errors.append(f"✗ Database connection failed: {e}")
    try:
        from sqlalchemy import text
        with _session(cfg) as sess:
            row = sess.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_name = 'memories_v2'"
            )).scalar()
        if row:
            print("✓ Schema OK (memories_v2 exists)")
        else:
            errors.append("✗ memories_v2 table missing — run: memory-mcp init")
    except Exception as e:
        errors.append(f"✗ Schema check failed: {e}")
    print(f"✓ Config: {Path.home() / '.memory-mcp' / 'config.json'}")
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    cfg = _config()
    with _session(cfg) as sess:
        store = MemoryStore(sess, cfg)
        results = store.search(
            query=args.query,
            scopes=[args.scope] if args.scope else None,
            limit=args.limit,
        )
    for r in results:
        print(f"[{r.id[:8]}] ({r.kind}/{r.scope}) {r.title}")
        print(f"  {r.summary[:120]}")
    print(f"\n{len(results)} result(s)")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    cfg = _config()
    with _session(cfg) as sess:
        results = MemoryStore(sess, cfg).get([args.id])
    if not results:
        print(f"No memory found with id {args.id}", file=sys.stderr)
        return 1
    r = results[0]
    print(json.dumps({
        "id": r.id, "title": r.title, "summary": r.summary, "details": r.details,
        "kind": r.kind, "scope": r.scope, "tags": r.tags,
        "confidence": r.confidence, "created_at": r.created_at,
    }, indent=2))
    return 0


def cmd_save(args: argparse.Namespace) -> int:
    cfg = _config()
    with _session(cfg) as sess:
        store = MemoryStore(sess, cfg)
        mid, updated = store.save(
            title=args.title, summary=args.summary,
            details=args.details, kind=args.kind or "note",
            scope=args.scope or "global",
        )
        sess.commit()
    action = "Updated" if updated else "Saved"
    print(f"{action}: {mid}")
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    cfg = _config()
    with _session(cfg) as sess:
        store = MemoryStore(sess, cfg)
        mid, resume = store.checkpoint(
            task=args.task, state=args.state,
            next_steps=args.next_steps or [],
            scope=args.scope or "project",
        )
        sess.commit()
    print(f"Checkpoint saved: {mid}")
    print(resume)
    return 0


def cmd_timeline(args: argparse.Namespace) -> int:
    cfg = _config()
    with _session(cfg) as sess:
        store = MemoryStore(sess, cfg)
        results = store.timeline(
            scopes=[args.scope] if args.scope else None,
            since=args.since, limit=args.limit or 20,
        )
    for r in results:
        print(f"[{r.created_at[:10]}] ({r.kind}) {r.title}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    cfg = _config()
    from sqlalchemy import text
    with _session(cfg) as sess:
        rows = sess.execute(text("SELECT * FROM memories_v2 ORDER BY created_at")).fetchall()
    memories = [dict(r._mapping) for r in rows]
    for m in memories:
        if hasattr(m.get("created_at"), "isoformat"):
            m["created_at"] = m["created_at"].isoformat()
        if hasattr(m.get("updated_at"), "isoformat"):
            m["updated_at"] = m["updated_at"].isoformat()
    if args.format == "json":
        print(json.dumps(memories, indent=2, default=str))
    else:
        for m in memories:
            print(f"## {m['title']}\n**Kind:** {m['kind']} | **Scope:** {m['scope']}\n\n{m['summary']}\n")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    path = Path(args.file)
    memories = json.loads(path.read_text(encoding="utf-8"))
    cfg = _config()
    from sqlalchemy import text
    inserted = skipped = 0
    with _session(cfg) as sess:
        for m in memories:
            exists = sess.execute(
                text("SELECT 1 FROM memories_v2 WHERE id = :id"), {"id": m["id"]}
            ).fetchone()
            if exists:
                skipped += 1
                continue
            sess.execute(
                text("""
                    INSERT INTO memories_v2
                        (id, title, summary, details, kind, scope, workspace_id,
                         project_id, tags, source, confidence, created_at, updated_at,
                         supersedes_id, metadata)
                    VALUES
                        (:id, :title, :summary, :details, :kind, :scope, :workspace_id,
                         :project_id, :tags::jsonb, :source, :confidence, :created_at,
                         :updated_at, :supersedes_id, :metadata::jsonb)
                """),
                {
                    "id": m["id"], "title": m["title"], "summary": m["summary"],
                    "details": m.get("details"), "kind": m.get("kind", "note"),
                    "scope": m.get("scope", "global"),
                    "workspace_id": m.get("workspace_id"),
                    "project_id": m.get("project_id"),
                    "tags": json.dumps(m.get("tags", [])),
                    "source": m.get("source"), "confidence": m.get("confidence", 1.0),
                    "created_at": m.get("created_at", "now()"),
                    "updated_at": m.get("updated_at", "now()"),
                    "supersedes_id": m.get("supersedes_id"),
                    "metadata": json.dumps(m.get("metadata", {})),
                },
            )
            inserted += 1
        sess.commit()
    print(f"Imported {inserted}, skipped {skipped} duplicates.")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    cfg = _config()
    with _session(cfg) as sess:
        store = MemoryStore(sess, cfg)
        result = store.prune(
            dry_run=not args.no_dry_run,
            older_than_days=args.older_than_days,
        )
        if not args.no_dry_run:
            sess.commit()
    print(json.dumps(result, indent=2))
    return 0


def cmd_server(args: argparse.Namespace) -> int:
    if args.transport == "http":
        from memory_mcp.tools.server import run_http
        run_http(port=args.port)
    else:
        from memory_mcp.tools.server import run_stdio
        run_stdio()
    return 0


def cmd_migrate_from_legacy(args: argparse.Namespace) -> int:
    from memory_mcp.migrate.legacy import migrate_from_legacy
    cfg = _config()
    with _session(cfg) as sess:
        report = migrate_from_legacy(
            sess, dry_run=args.dry_run, include_archived=args.include_archived
        )
        if not args.dry_run:
            sess.commit()
    print(json.dumps(report, indent=2))
    return 0


def cmd_drop_legacy(args: argparse.Namespace) -> int:
    from memory_mcp.migrate.legacy import drop_legacy
    cfg = _config()
    with _session(cfg) as sess:
        drop_legacy(sess)
        sess.commit()
    print("Legacy tables dropped.")
    return 0


# ── parser ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory-mcp", description="Local memory MCP server.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialise ~/.memory-mcp/ and run migrations")
    sub.add_parser("doctor", help="Check DB, schema, config")

    p = sub.add_parser("search", help="Slim FTS search")
    p.add_argument("query"); p.add_argument("--scope"); p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("get", help="Full record by ID")
    p.add_argument("id")

    p = sub.add_parser("save", help="Save a memory")
    p.add_argument("--title", required=True); p.add_argument("--summary", required=True)
    p.add_argument("--details"); p.add_argument("--kind"); p.add_argument("--scope")

    p = sub.add_parser("checkpoint", help="Save a resumable checkpoint")
    p.add_argument("--task", required=True); p.add_argument("--state", required=True)
    p.add_argument("--next-steps", nargs="*", dest="next_steps")
    p.add_argument("--scope", default="project")

    p = sub.add_parser("timeline", help="Recent memories in order")
    p.add_argument("--scope"); p.add_argument("--since"); p.add_argument("--limit", type=int)

    p = sub.add_parser("export", help="Export all memories")
    p.add_argument("--format", choices=["json", "markdown"], default="json")

    p = sub.add_parser("import", help="Import from export file")
    p.add_argument("file")

    p = sub.add_parser("prune", help="Prune stale memories")
    p.add_argument("--no-dry-run", action="store_true", help="Actually delete (default is dry-run)")
    p.add_argument("--older-than-days", type=int, dest="older_than_days")

    p = sub.add_parser("migrate-from-legacy", help="Migrate old schema to memories_v2")
    p.add_argument("--dry-run", action="store_true", default=False)
    p.add_argument("--include-archived", action="store_true", dest="include_archived")

    sub.add_parser("drop-legacy", help="Drop _legacy tables after verifying migration")

    p = sub.add_parser("server", help="Start MCP server")
    p.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    p.add_argument("--port", type=int, default=8080)

    return parser


_HANDLERS = {
    "init": cmd_init, "doctor": cmd_doctor, "search": cmd_search,
    "get": cmd_get, "save": cmd_save, "checkpoint": cmd_checkpoint,
    "timeline": cmd_timeline, "export": cmd_export, "import": cmd_import,
    "prune": cmd_prune, "migrate-from-legacy": cmd_migrate_from_legacy,
    "drop-legacy": cmd_drop_legacy, "server": cmd_server,
}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = _HANDLERS.get(args.command)
    if handler is None:
        parser.print_help(); sys.exit(1)
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Update src/memory_mcp/main.py**

```python
"""Entry point — delegates to CLI."""
from __future__ import annotations
from memory_mcp.cli.main import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run CLI tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_cli.py -v 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add src/memory_mcp/cli/ src/memory_mcp/main.py tests/test_cli.py
git commit -m "feat: add 13-subcommand CLI (init/doctor/search/get/save/checkpoint/timeline/export/import/prune/migrate/server)"
```

---

## Task 11: Legacy Migration

**Files:**
- Create: `src/memory_mcp/migrate/__init__.py`
- Create: `src/memory_mcp/migrate/legacy.py`
- Create: `tests/test_legacy_migration.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_legacy_migration.py
from __future__ import annotations
import json
import pytest
from sqlalchemy import text
from memory_mcp.migrate.legacy import _map_kind, _map_scope, migrate_from_legacy


def test_map_kind_coding_preference():
    assert _map_kind("coding_preference") == "preference"


def test_map_kind_project_fact():
    assert _map_kind("project_fact") == "architecture"


def test_map_kind_unknown_falls_back_to_note():
    assert _map_kind("something_weird") == "note"


def test_map_scope_global():
    assert _map_scope("global") == "global"


def test_map_scope_component_becomes_project():
    assert _map_scope("component") == "project"


def test_migrate_from_legacy_dry_run(session):
    # Insert a fake legacy row to migrate
    session.execute(text("""
        INSERT INTO memories_legacy
            (id, memory_type, summary, content, confidence, status, sensitivity,
             applies_to, created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'coding_preference', 'Use type hints everywhere',
             'Always annotate function signatures with types.', 0.9, 'active', 'normal',
             '{"memory_scope": "global"}'::jsonb, now(), now())
    """))
    session.flush()

    report = migrate_from_legacy(session, dry_run=True)
    assert report["would_migrate"] >= 1
    assert report["dry_run"] is True
    # Dry run: nothing in memories_v2
    count = session.execute(text("SELECT COUNT(*) FROM memories_v2")).scalar()
    assert count == 0
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_legacy_migration.py -v -k "not dry_run" 2>&1 | tail -15
```

Expected: `ImportError`.

- [ ] **Step 3: Create migrate/__init__.py**

```python
"""Legacy schema migration utilities."""
```

- [ ] **Step 4: Write migrate/legacy.py**

```python
"""Migrate memories from old schema (memories_legacy) to memories_v2."""
from __future__ import annotations

import json
import uuid
from sqlalchemy import text
from sqlalchemy.orm import Session

_KIND_MAP = {
    "coding_preference": "preference",
    "project_fact": "architecture",
    "component_summary": "architecture",
    "project_rule": "decision",
    "app_knowledge": "architecture",
    "episodic": "note",
    "ephemeral_note": "note",
    "inferred_preference": "preference",
    "entertainment_preference": "preference",
    "personal_fact": "note",
    "medication": "note",
    "environment_fact": "environment",
    "workflow": "workflow",
}

_SKIP_STATUSES = {"archived", "superseded", "deleted"}


def _map_kind(memory_type: str) -> str:
    return _KIND_MAP.get(memory_type, "note")


def _map_scope(memory_scope: str) -> str:
    mapping = {"global": "global", "workspace": "workspace",
               "project": "project", "component": "project"}
    return mapping.get(memory_scope, "global")


def migrate_from_legacy(
    session: Session,
    *,
    dry_run: bool = True,
    include_archived: bool = False,
) -> dict:
    """Read memories_legacy and write to memories_v2. Returns migration report."""
    skip_statuses = list(_SKIP_STATUSES) if not include_archived else []
    where = ""
    params: dict = {}
    if skip_statuses:
        where = "WHERE status NOT IN :skip"
        params["skip"] = tuple(skip_statuses)

    rows = session.execute(
        text(f"SELECT * FROM memories_legacy {where}"), params
    ).fetchall()

    migrated = skipped_status = 0
    unmapped_kinds: set[str] = set()

    for row in rows:
        if not include_archived and getattr(row, "status", "active") in _SKIP_STATUSES:
            skipped_status += 1
            continue

        applies_to = row.applies_to or {}
        memory_scope = applies_to.get("memory_scope", "global")
        scope = _map_scope(memory_scope)
        kind = _map_kind(getattr(row, "memory_type", ""))
        if getattr(row, "memory_type", "") not in _KIND_MAP:
            unmapped_kinds.add(getattr(row, "memory_type", "unknown"))

        workspace_name = applies_to.get("workspace")
        project_name = applies_to.get("project") or applies_to.get("component")

        workspace_id = None
        project_id = None

        if not dry_run:
            from memory_mcp.store.projects import ProjectStore
            ps = ProjectStore(session)
            if workspace_name:
                workspace_id = ps.get_or_create(name=workspace_name, kind="workspace")
            if project_name:
                project_id = ps.get_or_create(name=project_name, kind="project")

            # Aggregate tags from memory_tags_legacy
            tag_rows = session.execute(
                text("SELECT tag FROM memory_tags_legacy WHERE memory_id = :mid AND status = 'active'"),
                {"mid": row.id},
            ).fetchall()
            tags = [r.tag for r in tag_rows]

            summary = getattr(row, "summary", "") or ""
            content = getattr(row, "content", "") or ""

            session.execute(
                text("""
                    INSERT INTO memories_v2
                        (id, title, summary, details, kind, scope,
                         workspace_id, project_id, tags, confidence,
                         created_at, updated_at)
                    VALUES
                        (:id, :title, :summary, :details, :kind, :scope,
                         :workspace_id, :project_id, :tags::jsonb, :confidence,
                         :created_at, :updated_at)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": str(row.id),
                    "title": (summary[:120] if summary else f"Memory {str(row.id)[:8]}"),
                    "summary": summary[:2000],
                    "details": content[:10000] if content else None,
                    "kind": kind,
                    "scope": scope,
                    "workspace_id": workspace_id,
                    "project_id": project_id,
                    "tags": json.dumps(tags),
                    "confidence": float(getattr(row, "confidence", 1.0)),
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                },
            )
        migrated += 1

    return {
        "dry_run": dry_run,
        "would_migrate" if dry_run else "migrated": migrated,
        "skipped_status": skipped_status,
        "unmapped_kinds": sorted(unmapped_kinds),
    }


def drop_legacy(session: Session) -> None:
    """Drop all _legacy tables. Run only after verifying migrate_from_legacy."""
    for table in [
        "context_packet_memories_legacy", "context_packets_legacy",
        "pruning_log_legacy", "retrieval_profiles_legacy",
        "memory_tags_legacy", "relationships_legacy",
        "entities_legacy", "memories_legacy",
    ]:
        session.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
```

- [ ] **Step 5: Run migration tests (unit tests only — no live legacy data needed)**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_legacy_migration.py -v -k "not dry_run" 2>&1 | tail -15
```

Expected: `5 passed` (map tests).

- [ ] **Step 6: Run the actual migration against main database**

```powershell
.venv\Scripts\python.exe -m memory_mcp.cli.main migrate-from-legacy --dry-run
```

Expected: JSON report showing `would_migrate` count and any `unmapped_kinds`.

- [ ] **Step 7: Review dry-run output, then migrate for real**

```powershell
.venv\Scripts\python.exe -m memory_mcp.cli.main migrate-from-legacy
```

Expected: JSON report with `migrated` count.

- [ ] **Step 8: Verify in DB**

```powershell
docker compose exec postgres psql -U memory_mcp -d memory_mcp -c "SELECT scope, kind, COUNT(*) FROM memories_v2 GROUP BY scope, kind ORDER BY scope, kind;"
```

Expected: rows showing migrated memories by scope and kind.

- [ ] **Step 9: Commit**

```powershell
git add src/memory_mcp/migrate/ tests/test_legacy_migration.py
git commit -m "feat: add legacy schema migration (memories_legacy -> memories_v2)"
```

---

## Task 12: Export/Import Tests

**Files:**
- Create: `tests/test_export_import.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_export_import.py
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "memory_mcp.cli.main", *args],
        capture_output=True, text=True,
    )


def test_export_import_roundtrip(tmp_path):
    # Save a memory
    save_result = _run("save", "--title", "Export test memory",
                       "--summary", "This should survive export/import", "--scope", "global")
    assert save_result.returncode == 0, save_result.stderr

    # Export to JSON
    export_path = tmp_path / "export.json"
    export_result = _run("export", "--format", "json")
    assert export_result.returncode == 0
    export_path.write_text(export_result.stdout)

    memories = json.loads(export_path.read_text())
    assert any(m["title"] == "Export test memory" for m in memories)

    # Import into fresh run (duplicates should be skipped)
    import_result = _run("import", str(export_path))
    assert import_result.returncode == 0
    assert "skipped" in import_result.stdout
```

- [ ] **Step 2: Run tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_export_import.py -v 2>&1 | tail -15
```

Expected: `1 passed`.

- [ ] **Step 3: Commit**

```powershell
git add tests/test_export_import.py
git commit -m "test: add export/import round-trip test"
```

---

## Task 13: Benchmark Runner Update

**Files:**
- Modify: `benchmarks/outline_benchmark_runner.py`

- [ ] **Step 1: Find the seed step in the runner**

```powershell
Select-String -Path "D:\git\ai\memory-mcp\benchmarks\outline_benchmark_runner.py" -Pattern "add_memory|memory_type|applies_to" | Select-Object LineNumber, Line | head -20
```

- [ ] **Step 2: Update the seed step**

In `outline_benchmark_runner.py`, find the function that seeds benchmark memories (calls `add_memory` tool). Replace it with a call to `memory_save` using the new field mapping:

```python
def _seed_memory(client, memory: dict) -> None:
    """Seed a benchmark memory using the new memory_save tool."""
    applies_to = memory.get("applies_to", {})
    memory_scope = applies_to.get("memory_scope", "global")
    scope = {"global": "global", "workspace": "workspace",
             "project": "project", "component": "project"}.get(memory_scope, "global")
    kind_map = {
        "coding_preference": "preference", "project_fact": "architecture",
        "component_summary": "architecture", "project_rule": "decision",
    }
    kind = kind_map.get(memory.get("memory_type", ""), "note")
    client.call_tool("memory_save", {
        "title": memory.get("summary", "")[:120],
        "summary": memory.get("summary", ""),
        "details": memory.get("content"),
        "kind": kind,
        "scope": scope,
        "workspace_id": None,  # resolved by benchmark runner separately if needed
        "project_id": None,
    })
```

- [ ] **Step 3: Verify dry-run still works**

```powershell
.venv\Scripts\python.exe benchmarks/outline_benchmark_runner.py --dry-run 2>&1 | head -30
```

Expected: preflight output without errors.

- [ ] **Step 4: Commit**

```powershell
git add benchmarks/outline_benchmark_runner.py
git commit -m "fix: update benchmark runner seed step to use memory_save (new tool API)"
```

---

## Task 14: AGENT_MEMORY_POLICY.md

**Files:**
- Create: `docs/AGENT_MEMORY_POLICY.md`

- [ ] **Step 1: Write the policy doc**

```markdown
# Agent Memory Policy

Guidelines for agents using memory-mcp in coding workflows.

## Before Starting Work

1. Call `memory_search` with project + task keywords.
2. Call `memory_timeline` filtered to `kind=checkpoint` to find resumable sessions.
3. Call `memory_get` only for the top 2–3 IDs that look relevant.
4. Do not preload all memory. Do not call `memory_get` without first calling `memory_search`.

Alternatively, call `get_context_packet` with your request — it runs both stages internally.

## During Work

Save only durable, reusable facts:
- Architecture decisions (`kind=architecture`)
- Non-obvious commands that actually work (`kind=command`)
- Environment constraints discovered (`kind=environment`)
- Bugs found with root cause (`kind=bug`)
- Workflow preferences confirmed (`kind=preference`)

Do **not** save:
- Speculative notes or thoughts
- Information easily derivable from reading the code
- Anything inside `<private>...</private>`
- Secrets, API keys, tokens, passwords, or connection strings with credentials

## At the End of Long Work

Call `memory_checkpoint` with:
- `task`: what you were doing
- `state`: exactly where you stopped
- `next_steps`: the next 2–3 concrete actions
- `blockers`: anything that prevented completion
- `files_changed`: key files touched
- `commands_run`: commands that mattered

## Scope Guidelines

| Situation | Use scope |
|---|---|
| Universal rule applicable across all projects | `global` |
| Decision about how repos in the ecosystem relate | `workspace` |
| Fact about one specific repo | `project` |

Always pass `workspace_id` and/or `project_id` when saving project or workspace memories.

## Deduplication

The server deduplicates automatically: if your save title closely matches an existing memory in the same scope + kind, it updates that record instead of creating a new one. You do not need to check before saving.

## Cheap vs. Strong Agents

- **Cheap agents:** call `memory_search`, `memory_timeline`, `memory_get` for retrieval. Call `memory_save`, `memory_checkpoint` for writing. Do not call `get_context_packet` unless synthesis is needed.
- **Strong agents:** use `get_context_packet` when you need a synthesised context packet with quality assessment and source-read guidance.

## What Not To Do

- Do not dump all memory into context by calling `memory_get` with many IDs before searching.
- Do not use memory as a scratchpad for every thought.
- Do not save the same decision twice — prefer updating existing memories.
- Do not call `memory_delete` without a specific ID from a prior search.
```

- [ ] **Step 2: Commit**

```powershell
git add docs/AGENT_MEMORY_POLICY.md
git commit -m "docs: add AGENT_MEMORY_POLICY.md for agent memory usage guidelines"
```

---

## Task 15: Full Test Run + Acceptance Check

- [ ] **Step 1: Run the full test suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v 2>&1 | tail -40
```

Expected: all tests pass.

- [ ] **Step 2: Run doctor**

```powershell
.venv\Scripts\python.exe -m memory_mcp.cli.main doctor
```

Expected: all checks pass, exit 0.

- [ ] **Step 3: Verify all 9 MCP tools register**

```powershell
.venv\Scripts\python.exe -c "
from memory_mcp.tools.server import mcp
from memory_mcp.tools import context_packet
tools = [t.name for t in mcp._tool_manager.list_tools()]
print('\n'.join(sorted(tools)))
"
```

Expected output includes all 9:
```
get_context_packet
memory_checkpoint
memory_delete
memory_get
memory_prune
memory_save
memory_search
memory_timeline
memory_update
```

- [ ] **Step 4: Smoke test server startup**

```powershell
$proc = Start-Process -PassThru -NoNewWindow .venv\Scripts\python.exe -ArgumentList "-m memory_mcp.cli.main server"
Start-Sleep -Seconds 2
if (-not $proc.HasExited) { Write-Host "Server started OK"; $proc.Kill() } else { Write-Host "Server exited prematurely" }
```

Expected: `Server started OK`.

- [ ] **Step 5: Final commit**

```powershell
git add -A
git commit -m "chore: memory-mcp rewrite complete — memories_v2 schema, 9 MCP tools, 13-command CLI, legacy migration"
```

---

## Self-Review Against Spec

| Spec requirement | Task covering it |
|---|---|
| memories_v2 + projects schema | Task 3 |
| Three scopes: global/workspace/project | Tasks 6, 7 |
| Two-stage retrieval | Task 7 (search + get), Task 9 (context_packet) |
| 8 new MCP tools | Task 8 |
| get_context_packet retained | Task 9 |
| CLI 13 subcommands | Task 10 |
| Privacy: private block stripping | Task 5 |
| Privacy: secret detection | Task 5 |
| Legacy migration | Task 11 |
| Export/import | Task 10 (cmd_export/cmd_import) + Task 12 (tests) |
| Benchmark runner update | Task 13 |
| AGENT_MEMORY_POLICY.md | Task 14 |
| HTTP/SSE transport | Task 8 (run_http) + Task 10 (server subcommand) |
| Workspace detection | Task 4 |
| AppConfig (~/.memory-mcp/config.json) | Task 2 |
| All tests pass | Task 15 |
| doctor passes | Task 15 |
