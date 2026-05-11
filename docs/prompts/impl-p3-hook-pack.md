# Implementation Prompt — P3 Client Hook Pack (UCX-Style Workspace)

**Model:** Haiku
**Estimated effort:** 2–4 hrs
**Branch:** `feat/p3-hook-pack`

## Context

Adds a reference client hook pack for UCX-style multi-repo workspaces.
Documentation and templates only — no application code changes.
Lives in `client-setups/ucx-workspace/`. Clearly labeled "reference, not required."

## Files to create

- `client-setups/ucx-workspace/README.md`
- `client-setups/ucx-workspace/ingest.manifest.yaml`
- `client-setups/ucx-workspace/AGENTS.md`
- `client-setups/ucx-workspace/hooks/pre-session-check.py`

## Step 1: Create client-setups/ucx-workspace/README.md

```markdown
# UCX-Style Workspace Hook Pack

Reference configuration for a multi-repo workspace using memory-mcp.
**This is optional** — copy what you need, ignore the rest.

## Contents

| File | Purpose |
|------|---------|
| `ingest.manifest.yaml` | Manifest template for `scripts/ingest_markdown_workspace.py` |
| `AGENTS.md` | Memory-first agent workflow description |
| `hooks/pre-session-check.py` | Pre-session hook that warns when the store is empty |

## Setup

1. Copy this folder into your workspace root (e.g. `ucx-root/.memory-mcp/`).
2. Edit `ingest.manifest.yaml` with your workspace name and repo list.
3. Run: `python scripts/ingest_markdown_workspace.py --workspace <name> --dir <root>`
4. Install the pre-session hook in your client (see `client-setups/claude-code/`).
```

## Step 2: Create client-setups/ucx-workspace/ingest.manifest.yaml

```yaml
# ingest.manifest.yaml — populate for your workspace
workspace: ucx-root  # change to your workspace name

sources:
  markdown:
    - glob: "ucx-ai/rules/*.mdc"
      memory_type: coding_preference
      memory_scope: workspace
    - glob: "ucx-ai/mermaid-diagrams/*.md"
      memory_type: architecture_decision
      memory_scope: workspace
    - glob: "*/README.md"
      memory_type: project_fact
      memory_scope: project
    - glob: "*/docs/ARCHITECTURE.md"
      memory_type: architecture_decision
      memory_scope: project
    - glob: "*/CLAUDE.md"
      memory_type: coding_preference
      memory_scope: project
    - glob: "*/docs/adr/*.md"
      memory_type: architecture_decision
      memory_scope: project

  repos:
    - name: UCX.UI
    - name: Ucx.CaseDetails
    - name: Ucx.RequestRouting
    - name: ucx.messages
    - name: evicore.gravity.common
    # add remaining repos here
```

## Step 3: Create client-setups/ucx-workspace/AGENTS.md

```markdown
# Memory-First Agent Workflow

This workspace uses memory-mcp for durable context across sessions.

## Before Starting Any Task

Call get_context_packet:
  workspace: "ucx-root"
  repo: "<current repo>"
  request: "<your task description>"

Check context_quality and suggested_next_action before reading source files.

## Scoping Convention

Use these parameters consistently:
  workspace: "ucx-root"          (always)
  repo: "<git repo name>"        (per-service work)
  component: "<layer>"           (Api/Application/Domain/Infrastructure/Observer)

## Storing New Memories

When you learn something durable, store it:

  add_memory(
    content="<fact>",
    memory_type="<type>",
    memory_scope="<scope>",
    workspace="ucx-root",
    repo="<repo>",
  )

## Event Contracts

For event-sourced facts, use memory_type="event_contract" with metadata:
  {
    "event_name": "...",
    "producers": [...],
    "consumers": [...]
  }

Use get_event_flow(event_name="...") to retrieve producer/consumer context.

## Cross-Service Questions

Use traverse_entity_graph to walk service relationships.
Use search_entities to find services, events, or features by name.
```

## Step 4: Create client-setups/ucx-workspace/hooks/pre-session-check.py

```python
#!/usr/bin/env python
"""Pre-session hook: warn if memory store appears empty for this workspace.

Install in Claude Code settings.json:
  "hooks": {
    "SessionStart": [{"command": "python /path/to/pre-session-check.py"}]
  }
"""
import json
import os
import subprocess
import sys

WORKSPACE = os.environ.get("MEMORY_MCP_WORKSPACE", "")
MCP_CMD = os.environ.get("MEMORY_MCP_CMD", "memory-mcp")

if not WORKSPACE:
    sys.exit(0)

try:
    result = subprocess.run(
        [MCP_CMD, "call", "get_memory_cache_state"],
        capture_output=True, text=True, timeout=5,
    )
    state = json.loads(result.stdout)
    memory_count = state.get("total_memories", 0)
    if memory_count < 10:
        print(
            f"[memory-mcp] WARNING: only {memory_count} memories for workspace '{WORKSPACE}'. "
            "Consider running: python scripts/ingest_markdown_workspace.py "
            f"--workspace {WORKSPACE} --dir <workspace-root>",
            file=sys.stderr,
        )
except Exception:
    pass  # hook must not block session start
```

## Step 5: Commit

```bash
git add client-setups/ucx-workspace/
git commit -m "docs(client-setups): add P3 UCX-style workspace hook pack"
```

## Merge

```bash
git checkout main
git merge feat/p3-hook-pack --no-ff -m "docs: add P3 UCX-style workspace client hook pack"
git push origin main
```

## Handoff prompt for Track 12

```
Continue memory-mcp roadmap. Track 11 (P3 hook pack) is complete and merged to main.
Next: Track 12 — read docs/prompts/impl-p3-hosted-mode.md and implement it.
Branch off main as feat/p3-hosted-mode. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 11 status from ⬜ to ✅ before starting Track 12.
```
