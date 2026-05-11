# Implementation Prompt — P2 Multi-Repo Benchmark Harness

**Model:** Sonnet
**Estimated effort:** 1 day
**Branch:** `feat/p2-benchmarks`

## Context

Adds a multi-repo benchmark harness to validate retrieval precision and recall
against a synthetic corpus that mimics a nine-service workspace. Run after
Tracks 2, 4, 5, 6 are merged.

## Relevant files

- Create: `benchmarks/multi_repo_cases.json` — 40+ benchmark cases
- Create: `benchmarks/run_multi_repo_benchmarks.py` — runner script
- Create: `benchmarks/corpus/__init__.py` — package marker
- Create: `benchmarks/corpus/seed_multi_repo_corpus.py` — corpus seeder
- Test: `tests/test_multi_repo_benchmarks.py` (smoke test)

## Synthetic corpus shape

```python
# benchmarks/corpus/seed_multi_repo_corpus.py
"""Seed synthetic multi-repo corpus for benchmark runs."""
from memory_mcp.db import session_scope
from memory_mcp.ingest.writer import IngestWriter

CORPUS = [
    # Workspace-level
    {"content": "UCX workspace contains 9 .NET microservices and 2 React SPAs.",
     "memory_type": "project_fact", "memory_scope": "workspace",
     "applies_to": {"workspace": "ucx-root"}},
    {"content": "The shared gravity library (evicore.gravity.common) provides base classes for all services.",
     "memory_type": "architecture_decision", "memory_scope": "workspace",
     "applies_to": {"workspace": "ucx-root"}},
    # Repo-level architecture decisions
    {"content": "UCX.RequestRouting decides reviewer by specialty and state license using RoutingService.",
     "memory_type": "architecture_decision", "memory_scope": "project",
     "applies_to": {"workspace": "ucx-root", "repo": "UCX.RequestRouting", "project": "UCX.RequestRouting"}},
    {"content": "Ucx.CaseDetails stores case state in CosmosDB via the observer pattern.",
     "memory_type": "project_fact", "memory_scope": "project",
     "applies_to": {"workspace": "ucx-root", "repo": "Ucx.CaseDetails", "project": "Ucx.CaseDetails"}},
    {"content": "UCX.UI has 24 feature folders organized by business domain.",
     "memory_type": "project_fact", "memory_scope": "component",
     "applies_to": {"workspace": "ucx-root", "repo": "UCX.UI", "component": "ui"}},
    {"content": "Ucx.RequestRouting uses Azure API Management routes defined in apim.tf.",
     "memory_type": "architecture_decision", "memory_scope": "project",
     "applies_to": {"workspace": "ucx-root", "repo": "UCX.RequestRouting"}},
    {"content": "All backend services follow Kafka event-sourcing: Observer → CosmosDB → API.",
     "memory_type": "architecture_decision", "memory_scope": "workspace",
     "applies_to": {"workspace": "ucx-root"}},
    {"content": "ucx.messages defines shared Kafka event contracts for all services.",
     "memory_type": "project_fact", "memory_scope": "project",
     "applies_to": {"workspace": "ucx-root", "repo": "ucx.messages", "project": "ucx.messages"}},
    # Event contracts
    {"content": "UserProfileConfigurationUpdated is produced by UCX.ConfigurationService and consumed by Ucx.RequestRouting.",
     "memory_type": "event_contract", "memory_scope": "workspace",
     "applies_to": {"workspace": "ucx-root"},
     "metadata": {"event_name": "UserProfileConfigurationUpdated",
                  "producers": [{"service": "UCX.ConfigurationService"}],
                  "consumers": [{"service": "Ucx.RequestRouting"}],
                  "schema_repo": "ucx.messages"}},
    {"content": "CaseStatusChanged is produced by Ucx.CaseDetails and consumed by UCX.UI and Ucx.RequestRouting.",
     "memory_type": "event_contract", "memory_scope": "workspace",
     "applies_to": {"workspace": "ucx-root"},
     "metadata": {"event_name": "CaseStatusChanged",
                  "producers": [{"service": "Ucx.CaseDetails"}],
                  "consumers": [{"service": "UCX.UI"}, {"service": "Ucx.RequestRouting"}]}},
    # Coding preferences
    {"content": "All .NET services use dependency injection via Microsoft.Extensions.DependencyInjection.",
     "memory_type": "coding_preference", "memory_scope": "workspace",
     "applies_to": {"workspace": "ucx-root"}},
    {"content": "React components use React Query for server state management.",
     "memory_type": "coding_preference", "memory_scope": "project",
     "applies_to": {"workspace": "ucx-root", "repo": "UCX.UI"}},
    # Component-level facts
    {"content": "UCX.RequestRouting.Application.Services contains business logic including RoutingService.",
     "memory_type": "project_fact", "memory_scope": "component",
     "applies_to": {"workspace": "ucx-root", "repo": "UCX.RequestRouting", "component": "Application"}},
    {"content": "UCX.RequestRouting.Observer handles Kafka messages and updates CosmosDB state.",
     "memory_type": "architecture_decision", "memory_scope": "component",
     "applies_to": {"workspace": "ucx-root", "repo": "UCX.RequestRouting", "component": "Observer"}},
    {"content": "Ucx.CaseDetails.Api exposes REST endpoints for case CRUD operations.",
     "memory_type": "project_fact", "memory_scope": "component",
     "applies_to": {"workspace": "ucx-root", "repo": "Ucx.CaseDetails", "component": "Api"}},
    # Add 25+ more entries following the same pattern to reach 40 total corpus entries.
    # Cover remaining services: UCX.ConfigurationService, Ucx.ReferenceData,
    # Ucx.Notifications, Ucx.Audit, ucx-ai. Add ADR-style decisions, deploy facts,
    # test strategy facts, and cross-service dependency facts.
]


def seed():
    with session_scope() as session:
        writer = IngestWriter(session)
        written = skipped = 0
        for entry in CORPUS:
            meta = entry.pop("metadata", None)
            result = writer.upsert(
                content=entry["content"],
                memory_type=entry["memory_type"],
                memory_scope=entry["memory_scope"],
                applies_to=entry.get("applies_to", {}),
                metadata=meta,
                tags=["benchmark:multi-repo"],
            )
            if result == "created":
                written += 1
            else:
                skipped += 1
        session.commit()
    print(f"Seeded: {written} written, {skipped} unchanged")


if __name__ == "__main__":
    seed()
```

## Benchmark cases format

Write `benchmarks/multi_repo_cases.json` with at least 40 cases:

```json
[
  {
    "id": "mr-001",
    "query": "How does request routing decide which reviewer to assign?",
    "workspace": "ucx-root",
    "repo": "UCX.RequestRouting",
    "gold_content_keywords": ["reviewer", "specialty", "state license", "RoutingService"],
    "expected_memory_types": ["architecture_decision"],
    "min_precision_at_8": 0.7
  },
  {
    "id": "mr-002",
    "query": "What services consume UserProfileConfigurationUpdated?",
    "workspace": "ucx-root",
    "gold_content_keywords": ["UserProfileConfigurationUpdated", "Ucx.RequestRouting"],
    "expected_memory_types": ["event_contract"],
    "min_precision_at_8": 0.7
  },
  {
    "id": "mr-003",
    "query": "How does Ucx.CaseDetails store state?",
    "workspace": "ucx-root",
    "repo": "Ucx.CaseDetails",
    "gold_content_keywords": ["CosmosDB", "observer"],
    "expected_memory_types": ["project_fact", "architecture_decision"],
    "min_precision_at_8": 0.7
  },
  {
    "id": "mr-004",
    "query": "What is the shared library used by all services?",
    "workspace": "ucx-root",
    "gold_content_keywords": ["gravity", "evicore"],
    "expected_memory_types": ["architecture_decision", "project_fact"],
    "min_precision_at_8": 0.6
  },
  {
    "id": "mr-005",
    "query": "How are API routes defined for UCX.RequestRouting?",
    "workspace": "ucx-root",
    "repo": "UCX.RequestRouting",
    "gold_content_keywords": ["APIM", "apim.tf", "API Management"],
    "expected_memory_types": ["architecture_decision"],
    "min_precision_at_8": 0.7
  }
]
```

Write the remaining 35+ cases covering: workspace-wide architectural patterns,
per-repo tech stack facts, event contract queries, component-level queries,
coding preference queries, cross-service dependency queries, and deploy/infra facts.
Use realistic queries an engineer would actually ask.

## Runner script

```python
# benchmarks/run_multi_repo_benchmarks.py
#!/usr/bin/env python
"""Run multi-repo benchmark cases against a live memory-mcp DB."""
import argparse
import json
import datetime
from pathlib import Path
from memory_mcp.db import session_scope
from memory_mcp.retrieval.service import HybridRetrievalService


def precision_at_k(results, gold_keywords, k=8):
    top_k = results[:k]
    hits = sum(
        1 for r in top_k
        if any(kw.lower() in r.memory.content.lower() for kw in gold_keywords)
    )
    return hits / min(k, len(top_k)) if top_k else 0.0


def run_case(case: dict) -> dict:
    with session_scope() as session:
        retrieval = HybridRetrievalService(session)
        applies_to = {"workspace": case["workspace"]}
        if case.get("repo"):
            applies_to["repo"] = case["repo"]
        results = retrieval.search_memories(
            text_query=case["query"],
            applies_to=applies_to,
            limit=8,
        )
        prec = precision_at_k(results, case["gold_content_keywords"])
        return {
            "id": case["id"],
            "query": case["query"],
            "precision_at_8": round(prec, 3),
            "pass": prec >= case.get("min_precision_at_8", 0.7),
            "result_count": len(results),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()

    if args.seed:
        from benchmarks.corpus.seed_multi_repo_corpus import seed
        seed()

    cases = json.loads(Path("benchmarks/multi_repo_cases.json").read_text())
    results = [run_case(c) for c in cases]

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    avg_prec = sum(r["precision_at_8"] for r in results) / total if total else 0

    print(f"\nResults: {passed}/{total} passed | avg precision@8: {avg_prec:.3f}")
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        print(f"  {status} {r['id']} p@8={r['precision_at_8']:.3f} ({r['result_count']} results)")

    if avg_prec < 0.7:
        print("\nWARNING: average precision@8 below 0.7 threshold")

    if args.report:
        out = Path("benchmarks/results") / f"multi-repo-{datetime.date.today()}.json"
        out.write_text(json.dumps({
            "date": str(datetime.date.today()),
            "avg_precision_at_8": round(avg_prec, 3),
            "passed": passed, "total": total,
            "cases": results,
        }, indent=2))
        print(f"Report written to {out}")


if __name__ == "__main__":
    main()
```

## Smoke test

```python
# tests/test_multi_repo_benchmarks.py
import json
from pathlib import Path


def test_benchmark_cases_file_exists_and_has_40_cases():
    cases = json.loads(Path("benchmarks/multi_repo_cases.json").read_text())
    assert len(cases) >= 40


def test_each_case_has_required_fields():
    cases = json.loads(Path("benchmarks/multi_repo_cases.json").read_text())
    for case in cases:
        assert "id" in case, f"missing id in {case}"
        assert "query" in case, f"missing query in {case}"
        assert "gold_content_keywords" in case, f"missing gold_content_keywords in {case}"
        assert isinstance(case["gold_content_keywords"], list)
        assert len(case["gold_content_keywords"]) >= 1
```

## Run

```bash
pytest tests/test_multi_repo_benchmarks.py -v
python benchmarks/run_multi_repo_benchmarks.py --seed --report
```

## Merge

```bash
git checkout main
git merge feat/p2-benchmarks --no-ff -m "feat: add P2 multi-repo benchmark harness"
git push origin main
```

## Handoff prompt for Track 11

```
Continue memory-mcp roadmap. Track 10 (P2 benchmarks) is complete and merged to main.
Next: Track 11 — read docs/prompts/impl-p3-hook-pack.md and implement it.
Branch off main as feat/p3-hook-pack. Use Haiku.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 10 status from ⬜ to ✅ before starting Track 11.
```
