# Implementation Prompt — P2 Event-Flow Memory Types + get_event_flow Tool

**Model:** Sonnet
**Estimated effort:** 3–5 hrs
**Branch:** `feat/p2-event-flow`

## Context

Adds two new memory types (`event_contract`, `service_dependency`) and a new MCP
tool `get_event_flow(event_name)` for event-sourced programs like ucx-root.
This is convention-based (stored in JSONB metadata), not a schema change.

## Relevant files

- Modify: `src/memory_mcp/models/types.py` — add new memory types to the valid set
- Modify: `src/memory_mcp/mcp_tools/server.py` — add `get_event_flow` tool
- Modify: `src/memory_mcp/services/context_synthesis.py` — include event flow in packet
- Test: `tests/test_event_flow.py` (new)

## Canonical metadata shape for event_contract

```json
{
  "event_name": "UserProfileConfigurationUpdated",
  "producers": [{"service": "UCX.ConfigurationService", "file": "..."}],
  "consumers": [{"service": "Ucx.RequestRouting", "handler": "..."}],
  "schema_repo": "ucx.messages",
  "schema_symbol": "UserProfileConfigurationUpdatedEvent"
}
```

## Step 1: Read types.py

Read `src/memory_mcp/models/types.py`. Understand how memory types are defined.
Add `"event_contract"` and `"service_dependency"` to the valid set.
Match the existing pattern exactly (list, TypedDict, Enum, or literal set).

## Step 2: Write failing tests

```python
# tests/test_event_flow.py

def test_add_event_contract_memory(mcp_client):
    result = mcp_client.call("add_memory", {
        "content": "UserProfileConfigurationUpdated is produced by UCX.ConfigurationService.",
        "memory_type": "event_contract",
        "memory_scope": "workspace",
        "workspace": "ucx-root",
        "tags": ["event:UserProfileConfigurationUpdated"],
        "metadata": {
            "event_name": "UserProfileConfigurationUpdated",
            "producers": [{"service": "UCX.ConfigurationService"}],
            "consumers": [{"service": "Ucx.RequestRouting"}],
            "schema_repo": "ucx.messages",
        },
    })
    assert result["status"] == "created"


def test_get_event_flow_returns_producers_and_consumers(mcp_client):
    mcp_client.call("add_memory", {
        "content": "OrderCreated is produced by OrderService.",
        "memory_type": "event_contract",
        "memory_scope": "workspace",
        "workspace": "test-ws",
        "metadata": {
            "event_name": "OrderCreated",
            "producers": [{"service": "OrderService"}],
            "consumers": [{"service": "InventoryService"}],
        },
    })
    result = mcp_client.call("get_event_flow", {"event_name": "OrderCreated", "workspace": "test-ws"})
    assert result["event_name"] == "OrderCreated"
    assert len(result["producers"]) >= 1
    assert len(result["consumers"]) >= 1


def test_get_event_flow_empty_when_not_found(mcp_client):
    result = mcp_client.call("get_event_flow", {"event_name": "NonExistentEvent"})
    assert result["count"] == 0
```

## Step 3: Add get_event_flow MCP tool in server.py

Before `run()`:

```python
@mcp.tool()
def get_event_flow(
    event_name: str,
    workspace: str | None = None,
    repo: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Return producers, consumers, and handlers for a named event."""
    event_name = _validate_text("event_name", event_name, max_chars=500)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    repo = _validate_text("repo", repo, max_chars=200)
    project = _validate_text("project", project, max_chars=200) or repo
    _authorize_tool_call("get_event_flow", AuthAction.READ, workspace=workspace, project=project)

    with session_scope() as session:
        from memory_mcp.models.schema import Memory
        from sqlalchemy import func

        q = session.query(Memory).filter(
            Memory.memory_type == "event_contract",
            Memory.status == "active",
        )
        if workspace:
            q = q.filter(Memory.applies_to["workspace"].astext == workspace)

        # Filter by event_name in metadata
        memories = [
            m for m in q.limit(100).all()
            if (m.metadata_ or {}).get("event_name") == event_name
        ]

        producers: list[dict] = []
        consumers: list[dict] = []
        schema_info: dict = {}
        for m in memories:
            meta = m.metadata_ or {}
            producers.extend(meta.get("producers", []))
            consumers.extend(meta.get("consumers", []))
            if not schema_info:
                schema_info = {k: meta[k] for k in ("schema_repo", "schema_symbol") if k in meta}

        return {
            "event_name": event_name,
            "count": len(memories),
            "producers": producers,
            "consumers": consumers,
            "schema": schema_info,
            "memory_ids": [str(m.id) for m in memories],
        }
```

Note: if the Memory model uses `metadata` instead of `metadata_` as the column
attribute name, adjust accordingly. Check `src/memory_mcp/models/schema.py` first.

## Step 4: Context synthesis — include event flow in packet

In `context_synthesis.py`, in the `synthesize` method, after building the facts
list, add a lightweight scan for event contracts matching the request text:

```python
# Check for event contract mentions in request
if session:  # only if a session is available in scope
    event_memories = session.query(Memory).filter(
        Memory.memory_type == "event_contract",
        Memory.status == "active",
        Memory.content.ilike(f"%{request[:80].replace('%', '')}%"),
    ).limit(3).all()
    for em in event_memories:
        meta = em.metadata_ or {}
        if meta.get("event_name"):
            packet_facts.append(
                f"Event {meta['event_name']}: "
                f"produced by {[p.get('service') for p in meta.get('producers', [])]},"
                f" consumed by {[c.get('service') for c in meta.get('consumers', [])]}"
            )
```

Adapt the variable names to match the existing `synthesize` implementation.

## Step 5: Run tests

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_event_flow.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p2-event-flow --no-ff -m "feat: add P2 event-flow memory types and get_event_flow tool"
git push origin main
```

## Handoff prompt for Track 8

```
Continue memory-mcp roadmap. Track 7 (P2 event-flow) is complete and merged to main.
Next: Track 8 — read docs/prompts/impl-p2-packet-diagnostics.md and implement it.
Branch off main as feat/p2-packet-diagnostics. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 7 status from ⬜ to ✅ before starting Track 8.
```
