# Implementation Prompt — Verify / Complete P0 Semantic Retrieval

**Model:** Sonnet
**Estimated effort:** 2–4 hrs (likely much less — most is already done)
**Branch:** `feat/p0-semantic-retrieval`

## Context

The embedding pipeline was partially implemented in a prior session. Migration `0006`
(HNSW index), `scripts/backfill_embeddings.py`, and `src/memory_mcp/embeddings/`
are all on main. This track verifies the hybrid retrieval blend is wired up correctly
and fills any gaps.

## Step 1: Audit before coding

Run these checks first. If all pass, this track may need zero code changes.

```bash
# 1. Confirm migration 0006 ran
python -c "
from memory_mcp.db import session_scope
from sqlalchemy import text
with session_scope() as s:
    r = s.execute(text(\"SELECT indexname FROM pg_indexes WHERE tablename='memories' AND indexname LIKE '%embedding%'\")).fetchall()
    print('Embedding indexes:', r)
"

# 2. Run embedding tests
pytest tests/embeddings/ tests/test_hybrid_retrieval_embedding.py -v

# 3. Check embedding config
python -c "from memory_mcp.embeddings.config import EmbeddingConfig; c = EmbeddingConfig(); print('enabled:', c.enabled, 'model:', c.model)"
```

## Step 2: Identify gaps

Read `src/memory_mcp/retrieval/service.py` and check:

1. Does `HybridRetrievalService.search_memories` call the embedding service when
   `text_query` is present?
2. Is there a hybrid score blend? Target weights: `0.35*vector + 0.35*text + 0.2*confidence + 0.1*recency`.
3. Is there a graceful fallback to FTS-only when embeddings are disabled or unavailable?

## Step 3: Implement missing pieces

Only implement what the audit reveals is missing. Common gaps:

**Gap A — Hybrid blend not wired:**
In `HybridRetrievalService.search_memories`, after FTS results are fetched, compute query
embedding via `EmbeddingService.embed(text_query)` and re-rank:

```python
# After FTS results are fetched:
if text_query and self._embedding_service.is_available():
    try:
        query_vec = self._embedding_service.embed(text_query)
        for result in results:
            if result.memory.embedding is not None:
                vec_score = cosine_similarity(query_vec, result.memory.embedding)
                result.rank_score = (
                    0.35 * vec_score
                    + 0.35 * result.text_rank
                    + 0.20 * result.confidence_score
                    + 0.10 * result.recency_score
                )
    except Exception:
        logger.warning("vector re-rank failed, using text rank only")
```

**Gap B — MEMORY_MCP_EMBEDDING_ENABLED not checked:**
Wrap embedding calls behind `EmbeddingConfig().enabled` so the server starts
cleanly without a local model.

**Gap C — Backfill script not connected to ingest:**
If `IngestWriter` does not call `EmbeddingService.embed` on new memories, add it.
Check `src/memory_mcp/ingest/writer.py` for the lazy embed call.

## Step 4: Write or update tests

If you added code in Step 3, add a test:

```python
# tests/test_hybrid_retrieval_embedding.py — add or extend
def test_hybrid_blend_degrades_gracefully_when_embedding_disabled(db_session):
    """FTS-only path must work when embedding is off."""
    with patch("memory_mcp.embeddings.config.EmbeddingConfig.enabled", False):
        svc = HybridRetrievalService(db_session)
        results = svc.search_memories(text_query="test query", limit=5)
        assert isinstance(results, list)
```

## Step 5: Run full test suite

```bash
pytest -v
```

## Step 6: If no gaps found

If audit passes and tests are green, this track is complete with no code changes.
Still create the branch, add a one-line ROADMAP.md update, and merge:

```bash
git checkout -b feat/p0-semantic-retrieval
# Update ROADMAP.md: Track 2 ⬜ → ✅
git add docs/prompts/ROADMAP.md
git commit -m "docs(roadmap): mark Track 2 semantic retrieval verified"
```

## Merge

```bash
git checkout main
git merge feat/p0-semantic-retrieval --no-ff -m "feat: verify and complete P0 semantic retrieval"
git push origin main
```

## Handoff prompt for Track 3

```
Continue memory-mcp roadmap. Track 2 (semantic retrieval) is complete and merged to main.
Next: Track 3 — read docs/prompts/impl-qw1-markdown-ingest.md and implement it.
Branch off main as feat/qw1-markdown-ingest. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 2 status from ⬜ to ✅ before starting Track 3.
```
