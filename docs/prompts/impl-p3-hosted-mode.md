# Implementation Prompt — P3 Hosted / Remote Mode Hardening

**Model:** Sonnet
**Estimated effort:** 4–8 hrs
**Branch:** `feat/p3-hosted-mode`

## Context

`MEMORY_MCP_AUTH_MODE=remote` already exists. This track adds per-tenant workspace
isolation enforcement, rate limiting per workspace, and deployment documentation.

## Relevant files

- Read first: `src/memory_mcp/auth/` — understand current auth layer
- Modify: `src/memory_mcp/auth/policy.py` — per-tenant isolation
- Create: `src/memory_mcp/auth/rate_limit.py` — rate limiter
- Modify: `src/memory_mcp/mcp_tools/server.py` — call rate limiter in authorize
- Create: `docs/hosted_deployment.md` — operator docs
- Test: `tests/test_auth_hosted.py` (new)

## Step 1: Read auth layer

Read `src/memory_mcp/auth/policy.py` and `tests/test_auth_policy.py` in full.
Understand how `AuthAction`, `_authorize_tool_call`, and workspace scoping work.
Note the current remote-mode behavior before modifying anything.

## Step 2: Write failing tests

```python
# tests/test_auth_hosted.py
import os
import pytest
from unittest.mock import patch


def test_remote_mode_rejects_cross_workspace_access():
    """Token for workspace A must not read workspace B."""
    with patch.dict(os.environ, {"MEMORY_MCP_AUTH_MODE": "remote"}):
        # Simulate a call where the token grants workspace-a but caller requests workspace-b
        # Exact implementation depends on how token_workspace is extracted in policy.py
        # Read policy.py to understand the call signature before writing this test
        pass  # fill in after reading policy.py


def test_rate_limit_blocks_after_threshold():
    from memory_mcp.auth.rate_limit import check_rate_limit, _buckets
    _buckets.clear()
    with patch.dict(os.environ, {"MEMORY_MCP_RATE_LIMIT_WRITES_PER_MIN": "3"}):
        check_rate_limit("ws-a", "write")
        check_rate_limit("ws-a", "write")
        check_rate_limit("ws-a", "write")
        with pytest.raises(PermissionError, match="Rate limit"):
            check_rate_limit("ws-a", "write")


def test_rate_limit_separate_per_workspace():
    from memory_mcp.auth.rate_limit import check_rate_limit, _buckets
    _buckets.clear()
    with patch.dict(os.environ, {"MEMORY_MCP_RATE_LIMIT_WRITES_PER_MIN": "1"}):
        check_rate_limit("ws-a", "write")
        # ws-b has its own bucket
        check_rate_limit("ws-b", "write")
```

## Step 3: Create rate_limit.py

```python
# src/memory_mcp/auth/rate_limit.py
import os
import time
import threading
from collections import defaultdict

_WRITE_LIMIT = int(os.environ.get("MEMORY_MCP_RATE_LIMIT_WRITES_PER_MIN", "60"))
_READ_LIMIT = int(os.environ.get("MEMORY_MCP_RATE_LIMIT_READS_PER_MIN", "300"))

_lock = threading.Lock()
_buckets: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(workspace: str, action: str) -> None:
    """Raise PermissionError if the workspace exceeds its per-minute limit."""
    limit = int(os.environ.get(
        "MEMORY_MCP_RATE_LIMIT_WRITES_PER_MIN" if action == "write"
        else "MEMORY_MCP_RATE_LIMIT_READS_PER_MIN",
        str(_WRITE_LIMIT if action == "write" else _READ_LIMIT),
    ))
    now = time.monotonic()
    key = f"{workspace}:{action}"
    with _lock:
        _buckets[key] = [t for t in _buckets[key] if now - t < 60]
        if len(_buckets[key]) >= limit:
            raise PermissionError(
                f"Rate limit exceeded for workspace '{workspace}' ({action}): "
                f"{limit} requests/min"
            )
        _buckets[key].append(now)
```

## Step 4: Per-tenant isolation in policy.py

Read `policy.py` to understand how the remote auth token provides the caller's
workspace claim. Add enforcement in `_authorize_tool_call` (or the equivalent
authorization function):

```python
# In remote mode, caller's workspace must match the token's workspace claim
auth_mode = os.environ.get("MEMORY_MCP_AUTH_MODE", "local")
if auth_mode == "remote" and workspace and token_workspace:
    if workspace != token_workspace:
        raise PermissionError(
            f"Workspace mismatch: token grants '{token_workspace}', "
            f"caller requested '{workspace}'"
        )
```

Also call rate limiter in remote mode:
```python
if auth_mode == "remote" and workspace:
    from memory_mcp.auth.rate_limit import check_rate_limit
    action_str = "write" if action == AuthAction.WRITE else "read"
    check_rate_limit(workspace, action_str)
```

## Step 5: Create docs/hosted_deployment.md

Write a deployment guide covering:
- Required env vars for remote mode (`MEMORY_MCP_AUTH_MODE`, `MEMORY_MCP_OIDC_*`,
  `MEMORY_MCP_RATE_LIMIT_*`, `DATABASE_URL`)
- Docker Compose production snippet (no dev volumes, healthcheck)
- Backup recommendation: `pg_dump` cron example
- Rate limit tuning guidance

## Step 6: Run tests

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
Update docs/prompts/ROADMAP.md: change Track 12 status from ⬜ to ✅.
Commit: git add docs/prompts/ROADMAP.md && git commit -m "docs(roadmap): mark Track 12 complete — roadmap done"
Run: pytest -v
Run: python benchmarks/run_multi_repo_benchmarks.py --seed --report
Push: git push origin main
```
