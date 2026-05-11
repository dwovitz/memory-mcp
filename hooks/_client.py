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
