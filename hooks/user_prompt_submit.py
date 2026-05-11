"""UserPromptSubmit hook: enqueue prompt + inject relevant memory context."""
from __future__ import annotations

import json
import os
import sys

from hooks._client import DEFAULT_BASE_URL, _http_post, enqueue


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
