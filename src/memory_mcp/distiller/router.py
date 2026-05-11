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

    Heuristics:
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
