# memory-mcp Completion Roadmap

Track status is updated after each merge to main.
Each prompt file is a cold-start implementation guide — load it in a fresh session.

## Handoff Prompt Template

Paste this into the next session after completing a track:

```
Continue memory-mcp roadmap. Track <N> (<name>) is complete and merged to main.
Next: Track <N+1> — read docs/prompts/<prompt-file> and implement it.
Branch off main as feat/<slug>. Use <model>.
Check docs/prompts/ROADMAP.md for current status before starting.
```

## Tracks

| # | Track | Prompt file | Branch | Model | Effort | Status |
|---|---|---|---|---|---|---|
| 0 | Branch cleanup + scaffold | *(this session)* | main | — | 15 min | ✅ |
| 1 | Auto-capture + distillation | [impl-auto-capture.md](impl-auto-capture.md) | `feat/auto-capture-distillation` | Sonnet | 1–2 days | ⬜ |
| 2 | Verify / complete semantic retrieval | [impl-semantic-retrieval.md](impl-semantic-retrieval.md) | `feat/p0-semantic-retrieval` | Sonnet | 2–4 hrs | ⬜ |
| 3 | QW1 markdown ingest script | [impl-qw1-markdown-ingest.md](impl-qw1-markdown-ingest.md) | `feat/qw1-markdown-ingest` | Sonnet | 2–4 hrs | ⬜ |
| 4 | P1 entity graph MCP tools | [impl-p1-entity-graph.md](impl-p1-entity-graph.md) | `feat/p1-entity-graph` | Sonnet | 4–8 hrs | ⬜ |
| 5 | P1 code citations + QW3 cited_path | [impl-p1-code-citations.md](impl-p1-code-citations.md) | `feat/p1-code-citations` | Sonnet | 4–6 hrs | ⬜ |
| 6 | P1 classifier upgrade | [impl-p1-classifier.md](impl-p1-classifier.md) | `feat/p1-classifier` | Sonnet | 4–6 hrs | ⬜ |
| 7 | P2 event-flow memory types | [impl-p2-event-flow.md](impl-p2-event-flow.md) | `feat/p2-event-flow` | Sonnet | 3–5 hrs | ⬜ |
| 8 | P2 context packet diagnostics | [impl-p2-packet-diagnostics.md](impl-p2-packet-diagnostics.md) | `feat/p2-packet-diagnostics` | Sonnet | 3–4 hrs | ⬜ |
| 9 | P2 code graph import tool | [impl-p2-code-graph-import.md](impl-p2-code-graph-import.md) | `feat/p2-code-graph-import` | Sonnet | 3–4 hrs | ⬜ |
| 10 | P2 multi-repo benchmark harness | [impl-p2-benchmarks.md](impl-p2-benchmarks.md) | `feat/p2-benchmarks` | Sonnet | 1 day | ⬜ |
| 11 | P3 client hook pack | [impl-p3-hook-pack.md](impl-p3-hook-pack.md) | `feat/p3-hook-pack` | Haiku | 2–4 hrs | ⬜ |
| 12 | P3 hosted mode hardening | [impl-p3-hosted-mode.md](impl-p3-hosted-mode.md) | `feat/p3-hosted-mode` | Sonnet | 4–8 hrs | ⬜ |

## Sequencing Constraints

- Track 6 (classifier) requires Track 4 (entity graph) to be merged first.
- Track 5 (code citations) must precede QW3 — they are bundled.
- Track 8 (packet diagnostics) benefits from Track 6 being done first.
- Track 10 (benchmarks) should run after Tracks 2, 4, 5, 6 are merged.
- Tracks 3, 4, 5 are independent and can be parallelized.
