# Implementation Prompt — P2 Context Packet Quality Signals (Multi-Repo Diagnostics)

**Model:** Sonnet
**Estimated effort:** 3–4 hrs
**Branch:** `feat/p2-packet-diagnostics`

## Context

`get_context_packet` returns a `context_quality` signal and `suggested_next_action`.
This track extends diagnostics with per-dimension signals useful for multi-repo
workspaces: which repos matched, which entities matched, which event names matched,
and per-layer memory counts. `suggested_next_action` also gets smarter branching.

Track 6 (classifier) should be merged before this track for best results.

## Relevant files

- Modify: `src/memory_mcp/services/context_synthesis.py` — extend diagnostics
- Modify: `src/memory_mcp/mcp_tools/server.py` — expose new fields in response (if needed)
- Test: `tests/test_context_synthesis.py` — extend

## Step 1: Read context_synthesis.py

Read the full file. Understand `ContextPacket` and how the `diagnostics` dict
is currently built. Note what fields are in the existing diagnostics output.

## Step 2: Write failing tests

```python
# tests/test_context_synthesis.py — add:

def test_diagnostics_include_matched_repos(synthesis_service, seeded_memories):
    packet = synthesis_service.synthesize(
        request="How does UCX.RequestRouting work?",
        workspace="ucx-root",
    )
    assert "matched_repos" in packet.diagnostics
    assert isinstance(packet.diagnostics["matched_repos"], list)


def test_diagnostics_include_per_layer_counts(synthesis_service, seeded_memories):
    packet = synthesis_service.synthesize(request="test", workspace="ucx-root")
    assert "per_layer_counts" in packet.diagnostics
    counts = packet.diagnostics["per_layer_counts"]
    assert isinstance(counts, dict)


def test_diagnostics_include_matched_event_names(synthesis_service, seeded_memories):
    packet = synthesis_service.synthesize(request="test", workspace="ucx-root")
    assert "matched_event_names" in packet.diagnostics
    assert isinstance(packet.diagnostics["matched_event_names"], list)
```

## Step 3: Extend diagnostics in synthesize()

After building the memory result list, collect:

```python
from collections import Counter

matched_repos = list({
    m.memory.applies_to.get("repo")
    for m in results
    if m.memory.applies_to and m.memory.applies_to.get("repo")
})

matched_entity_ids = list({
    str(m.memory.entity_id) for m in results if m.memory.entity_id
})

matched_event_names = [
    m.memory.metadata_.get("event_name")
    for m in results
    if m.memory.memory_type == "event_contract"
    and m.memory.metadata_
    and m.memory.metadata_.get("event_name")
]

per_layer_counts = dict(Counter(m.memory.memory_scope for m in results))
```

Note: `metadata_` may be named `metadata` in the model — check schema.py first.

Add to `diagnostics` dict:
```python
diagnostics.update({
    "matched_repos": matched_repos,
    "matched_entities": matched_entity_ids,
    "matched_event_names": matched_event_names,
    "per_layer_counts": per_layer_counts,
})
```

## Step 4: Upgrade suggested_next_action branching

Replace or extend the current suggestion logic with:

```python
def _suggest_next_action(context_quality: str, diagnostics: dict, classification) -> str:
    if context_quality == "strong":
        return "answer_from_packet"
    matched_repos = diagnostics.get("matched_repos", [])
    hinted_repos = getattr(classification, "hinted_repos", [])
    matched_entities = getattr(classification, "matched_entities", [])
    matched_event_names = diagnostics.get("matched_event_names", [])

    if hinted_repos and not matched_repos:
        return (
            f"run get_context_packet with repo={hinted_repos[0]!r} "
            "to narrow scope, or run search_memory with that repo filter"
        )
    if matched_entities and not matched_event_names:
        event_hit = next(
            (e["name"] for e in matched_entities
             if "event" in e.get("entity_type", "").lower()), None
        )
        if event_hit:
            return f"run get_event_flow(event_name={event_hit!r}) for event producer/consumer context"
    if matched_entities and not diagnostics.get("matched_repos"):
        eid = matched_entities[0]["id"]
        return f"run traverse_entity_graph(start_entity_id={eid!r}) for graph context"
    if context_quality == "weak":
        return "mark_weak_context — no strong matches; consider adding memories for this project"
    return "verify_narrowly"
```

Integrate this into `synthesize()` replacing or extending the existing suggestion logic.
Pass `classification` to it (from the existing classification step in synthesize).

## Step 5: Run tests

```bash
pytest tests/test_context_synthesis.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p2-packet-diagnostics --no-ff -m "feat: add P2 multi-repo context packet diagnostics"
git push origin main
```

## Handoff prompt for Track 9

```
Continue memory-mcp roadmap. Track 8 (P2 packet diagnostics) is complete and merged to main.
Next: Track 9 — read docs/prompts/impl-p2-code-graph-import.md and implement it.
Branch off main as feat/p2-code-graph-import. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 8 status from ⬜ to ✅ before starting Track 9.
```
