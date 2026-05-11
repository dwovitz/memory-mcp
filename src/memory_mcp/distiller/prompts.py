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
