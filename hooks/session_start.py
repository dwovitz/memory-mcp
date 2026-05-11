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
