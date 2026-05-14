# memory-mcp Context Packet Slimming

**Date:** 2026-05-14  
**Goal:** Reduce per-call token cost of `get_context_packet` without changing its behavioral contract.

---

## Problem

`get_context_packet` is called at the start of every substantial task. Each call includes:

1. ~500–800 tokens of static guidance prose in the rendered output (`_source_guidance_lines`)
2. Three redundant keys in the tool response dict: `source_read_limits` (30-key static dict), `source_read_contract` (20+ key nested dict), `diagnostics` (full blob containing both plus more)
3. No instruction to callers to reuse the packet within the same session — callers fetch fresh on every call

The static guidance is repeated verbatim on every call. It is never parsed programmatically — confirmed by grep: these keys appear only in `.jsonl` conversation history files. The cost is pure cache-read overhead that scales with session length.

---

## Design

### Section 1 — `context_synthesis.py`: slim `_source_guidance_lines()`

**Current behavior:** Emits 15–20 lines including DEGRADED_SEARCH_GUIDANCE, BOUNDED_SNIPPET_GUIDANCE, BOUNDED_SNIPPET_COUNT_GUIDANCE, pre-edit rules, fallback examples, implementation workflow paragraphs, and the full `source_read_limits` dict.

**New behavior:** Emit exactly 3 lines:

```python
lines = [
    f"Suggested next action: {suggested_next_action}.",
    f"Source read policy: {source_read_policy}.",
    f"Recommended post-packet source budget: {source_read_budget_tokens} tokens.",
]
return lines
```

Remove all static prose blocks. The three actionable values (suggested action, policy, budget) are all a caller needs; the prose is redundant with the project's CLAUDE.md.

### Section 1 — `server.py`: remove redundant keys from `_context_packet_to_dict()`

Remove three keys from the return dict:

```python
# Remove these:
"source_read_limits": packet.diagnostics.get("source_read_limits"),
"source_read_contract": packet.diagnostics.get("source_read_contract"),
"diagnostics": packet.diagnostics,
```

Keep all other keys unchanged. The scalar fields (`context_quality`, `warnings`, `suggested_next_action`, `source_read_policy`, `source_read_budget_tokens`) are already returned individually — the dicts are fully redundant.

**Estimated reduction:** ~1,400–2,000 tokens per call; ~42K–60K cache tokens saved per 30-turn session.

---

### Section 2 — `CLAUDE.md`: within-session skip pattern

The server already implements `if_cache_version`. If the caller passes the previous version token, the server returns `{"cached": True}` with zero DB reads. Nothing currently instructs callers to use this.

**Add to `CLAUDE.md`** under "Before Starting Any Substantial Work":

> **Within-session caching:** After the first `get_context_packet` call in a conversation, save the version token from the response. On every subsequent `get_context_packet` call in the same session, pass `if_cache_version: <saved_token>`. If the server returns `{"cached": True}`, reuse the previous packet — skip re-reading. Only fetch fresh if the server returns a new packet (memory changed between calls).

How to get the version token: it is available via `get_memory_cache_state` (cheap composite token) or from `token_estimates.cache_version` in a prior packet response.

**Effect:** First call per session = full fetch (unchanged). Calls 2–N = version check only, zero tokens consumed if memory is stable. If memory changes mid-session, the server detects the mismatch and returns a fresh packet automatically — no caller logic needed for invalidation.

**Cost impact:** A typical session makes 3–6 `get_context_packet` calls. With caching, calls 2–6 cost ~0 tokens instead of 500–800 each. Across the memory-mcp session (42.5M cache reads this period), reducing redundant fetches by 50% saves ~200–400K cache tokens per session.

---

## What Is Not Changing

- The `rendered` field content (beyond removal of the static guidance prose)
- All scalar fields returned by `_context_packet_to_dict()`
- The `if_cache_version` server implementation (already correct)
- Any memory storage or retrieval logic
- The `facts`, `episodic_context`, `evidence`, `preferences` fields

---

## Files to Modify

| File | Change |
|---|---|
| `src/memory_mcp/services/context_synthesis.py` | Replace `_source_guidance_lines()` body with 3-line version |
| `src/memory_mcp/mcp_tools/server.py` | Remove `source_read_limits`, `source_read_contract`, `diagnostics` from `_context_packet_to_dict()` |
| `CLAUDE.md` | Add `if_cache_version` skip pattern |
| `AGENTS.md` | Add `if_cache_version` skip pattern |
| `client-setups/codex/AGENTS.md` | Add `if_cache_version` skip pattern; remove `source_read_limits`/`source_read_contract` from inspect list; replace "Source Budget Contract" section with `source_read_policy` enum logic matching CLAUDE.md |
