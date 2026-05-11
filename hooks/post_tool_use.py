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
    text = json.dumps(resp, default=str)
    if len(text) > 4000:
        return text[:4000] + "...<truncated>"
    return resp


if __name__ == "__main__":
    sys.exit(main())
