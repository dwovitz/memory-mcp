# Implementation Prompt — P1 Classifier Upgrade (Two-Pass Entity Matching)

**Model:** Sonnet
**Estimated effort:** 4–6 hrs
**Branch:** `feat/p1-classifier`

## Context

`ContextSynthesisService` uses a lexical keyword classifier to determine request
domain. This track upgrades it to a two-pass classifier that also extracts matched
entities from the entity graph, exposing them in `RequestClassification` so that
retrieval can use entity-id hints and entity names for better precision.

Track 4 (entity graph tools) must be merged before this track starts.

## Relevant files

- Modify: `src/memory_mcp/services/context_synthesis.py` — extend classifier
- Modify: `src/memory_mcp/retrieval/service.py` — accept entity hints
- Test: `tests/test_context_synthesis.py` — extend existing tests

## Step 1: Read existing classifier

Read `src/memory_mcp/services/context_synthesis.py` in full. Understand:
- `RequestClassification` dataclass fields
- How `_classify_request` works (lexical matching)
- How `ContextSynthesisService.synthesize` uses the classification

## Step 2: Write failing tests

```python
# tests/test_context_synthesis.py — add to existing test file

def test_classification_exposes_matched_entities(synthesis_service):
    classification = synthesis_service.classify_request(
        "Why is UCX.RequestRouting not routing cases correctly?"
    )
    assert hasattr(classification, "matched_entities")
    assert hasattr(classification, "hinted_repos")
    assert hasattr(classification, "hinted_memory_types")


def test_classification_matched_entities_is_list(synthesis_service):
    classification = synthesis_service.classify_request("general question")
    assert isinstance(classification.matched_entities, list)
    assert isinstance(classification.hinted_repos, list)
    assert isinstance(classification.hinted_memory_types, list)
```

## Step 3: Extend RequestClassification

In `context_synthesis.py`, extend the `RequestClassification` dataclass:

```python
@dataclass
class RequestClassification:
    domain: str
    confidence: float
    matched_terms: list[str]
    # New fields (default to empty lists for backward compat):
    matched_entities: list[dict] = field(default_factory=list)
    hinted_memory_types: list[str] = field(default_factory=list)
    hinted_repos: list[str] = field(default_factory=list)
```

Use `from dataclasses import dataclass, field` — add `field` to import if missing.
Update all construction sites of `RequestClassification` to include the new fields
(pass `matched_entities=[]`, `hinted_memory_types=[]`, `hinted_repos=[]` where not yet set).

## Step 4: Add entity-matching pass to classifier

In `ContextSynthesisService`, add a private method:

```python
def _match_entities_in_request(self, request: str, session) -> list[dict]:
    """Run search_entities against the request text, return top hits."""
    try:
        from memory_mcp.retrieval.service import HybridRetrievalService
        retrieval = HybridRetrievalService(session)
        results = retrieval.search_entities(
            text_query=request,
            limit=5,
        )
        return [
            {"id": str(r.entity.id), "name": r.entity.name,
             "entity_type": r.entity.entity_type}
            for r in results
            if r.rank_score is None or r.rank_score > 0.3
        ]
    except Exception:
        return []
```

In `synthesize()` (or wherever classification happens with a session available),
call this method and populate `matched_entities`. Extract `hinted_repos` by checking
for entity hits where `entity_type in ("service", "repo")` and returning their names.
Extract `hinted_memory_types` from the existing domain classification mapping.

## Step 5: Pass entity hints to retrieval

In `synthesize()`, after classification, if `matched_entities` is non-empty,
pass entity IDs as hints to `search_memories`:

```python
entity_id_hints = [e["id"] for e in classification.matched_entities]
```

In `HybridRetrievalService.search_memories`, add `entity_id_hints: list[str] | None = None`.
When provided, boost results whose `memory.entity_id` is in the hint list:

```python
if entity_id_hints:
    entity_id_set = set(str(eid) for eid in entity_id_hints)
    for result in results:
        if str(result.memory.entity_id) in entity_id_set:
            result.rank_score = (result.rank_score or 0.0) + 0.1
```

## Step 6: Run tests

```bash
pytest tests/test_context_synthesis.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p1-classifier --no-ff -m "feat: add P1 two-pass entity-matching classifier upgrade"
git push origin main
```

## Handoff prompt for Track 7

```
Continue memory-mcp roadmap. Track 6 (P1 classifier) is complete and merged to main.
Next: Track 7 — read docs/prompts/impl-p2-event-flow.md and implement it.
Branch off main as feat/p2-event-flow. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 6 status from ⬜ to ✅ before starting Track 7.
```
