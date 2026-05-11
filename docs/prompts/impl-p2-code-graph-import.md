# Implementation Prompt — P2 Import Code Graph Summary Tool

**Model:** Sonnet
**Estimated effort:** 3–4 hrs
**Branch:** `feat/p2-code-graph-import`

## Context

Adds `import_code_graph_summary` MCP tool: accepts a bounded, schema-validated
JSON payload from an external code graph tool and writes the content as
`project_fact` or `architecture_decision` memories with code citations.
This is glue — memory-mcp does not parse code itself.

Track 5 (code citations) must be merged first — this tool uses `_validate_code_citations`
and passes `code_citations` through `IngestWriter.upsert`.

## Relevant files

- Modify: `src/memory_mcp/mcp_tools/server.py` — add tool
- Test: `tests/test_code_graph_import.py` (new)

## Accepted payload schema (versioned)

```json
{
  "schema_version": "1",
  "repo": "UCX.RequestRouting",
  "workspace": "ucx-root",
  "summaries": [
    {
      "memory_type": "architecture_decision",
      "content": "RoutingService decides reviewer by specialty and state license.",
      "scope": "component",
      "component": "routing",
      "code_citations": [
        {"repo": "UCX.RequestRouting",
         "path": "Application/Services/RoutingService.cs",
         "kind": "symbol",
         "symbol": "RoutingService.GetNextReviewer"}
      ],
      "tags": ["routing", "reviewer-selection"]
    }
  ]
}
```

Constraints:
- `schema_version` must be `"1"`
- `summaries` max 50 items
- Each `content` max 4000 chars
- Unknown top-level keys are rejected
- Unknown keys inside summaries are ignored (forward compat)

## Step 1: Write failing tests

```python
# tests/test_code_graph_import.py
import pytest

VALID_PAYLOAD = {
    "schema_version": "1",
    "repo": "UCX.RequestRouting",
    "workspace": "ucx-root",
    "summaries": [
        {
            "memory_type": "architecture_decision",
            "content": "RoutingService decides reviewer by specialty.",
            "scope": "component",
            "component": "routing",
            "code_citations": [
                {"repo": "UCX.RequestRouting",
                 "path": "Application/Services/RoutingService.cs",
                 "kind": "symbol"}
            ],
        }
    ],
}


def test_import_creates_memories(mcp_client):
    result = mcp_client.call("import_code_graph_summary", {"payload": VALID_PAYLOAD})
    assert result["created"] >= 1
    assert result["errors"] == []


def test_import_is_idempotent(mcp_client):
    r1 = mcp_client.call("import_code_graph_summary", {"payload": VALID_PAYLOAD})
    r2 = mcp_client.call("import_code_graph_summary", {"payload": VALID_PAYLOAD})
    assert r1["created"] >= 1
    assert r2["created"] == 0  # second run: all unchanged


def test_import_rejects_wrong_schema_version(mcp_client):
    bad = {**VALID_PAYLOAD, "schema_version": "99"}
    with pytest.raises(Exception, match="schema_version"):
        mcp_client.call("import_code_graph_summary", {"payload": bad})


def test_import_rejects_too_many_summaries(mcp_client):
    big = {**VALID_PAYLOAD, "summaries": [VALID_PAYLOAD["summaries"][0]] * 51}
    with pytest.raises(Exception, match="summaries"):
        mcp_client.call("import_code_graph_summary", {"payload": big})
```

## Step 2: Add tool to server.py

```python
_ALLOWED_IMPORT_TOP_KEYS = frozenset({"schema_version", "repo", "workspace", "summaries"})


@mcp.tool()
def import_code_graph_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept a code-graph summary payload and write it as typed memories."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    unknown = set(payload.keys()) - _ALLOWED_IMPORT_TOP_KEYS
    if unknown:
        raise ValueError(f"Unknown top-level keys: {sorted(unknown)}")
    if payload.get("schema_version") != "1":
        raise ValueError("schema_version must be '1'")
    summaries = payload.get("summaries", [])
    if not isinstance(summaries, list):
        raise ValueError("summaries must be a list")
    if len(summaries) > 50:
        raise ValueError("summaries must not exceed 50 items")

    repo_name = _validate_text("repo", payload.get("repo"), max_chars=200)
    workspace = _validate_text("workspace", payload.get("workspace"), max_chars=200)
    _authorize_tool_call(
        "import_code_graph_summary", AuthAction.WRITE,
        workspace=workspace, project=repo_name,
    )

    created = updated = skipped = 0
    errors: list[str] = []

    with session_scope() as session:
        from memory_mcp.ingest.writer import IngestWriter
        writer = IngestWriter(session)
        for i, summary in enumerate(summaries):
            try:
                content = summary.get("content", "")
                if len(content) > 4000:
                    raise ValueError("content exceeds 4000 chars")
                memory_type = summary.get("memory_type", "project_fact")
                citations = _validate_code_citations(summary.get("code_citations"))
                ingest_key_val = f"cgraph:{workspace}:{repo_name}:{i}:{hash(content) & 0xffffffff}"
                applies_to: dict[str, Any] = {}
                if workspace:
                    applies_to["workspace"] = workspace
                if repo_name:
                    applies_to[REPO_KEY] = repo_name
                    applies_to["project"] = repo_name
                if summary.get("component"):
                    applies_to["component"] = summary["component"]

                result = writer.upsert(
                    content=content,
                    memory_type=memory_type,
                    memory_scope=summary.get("scope", "project"),
                    applies_to=applies_to,
                    tags=list(summary.get("tags", [])) + ["ingest:code-graph"],
                    metadata={"ingest_key": ingest_key_val},
                    code_citations=citations,
                )
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors.append(f"summary[{i}]: {exc}")

        session.commit()

    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}
```

## Step 3: Run tests

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_code_graph_import.py -v
pytest -v
```

## Merge

```bash
git checkout main
git merge feat/p2-code-graph-import --no-ff -m "feat: add P2 import_code_graph_summary MCP tool"
git push origin main
```

## Handoff prompt for Track 10

```
Continue memory-mcp roadmap. Track 9 (P2 code graph import) is complete and merged to main.
Next: Track 10 — read docs/prompts/impl-p2-benchmarks.md and implement it.
Branch off main as feat/p2-benchmarks. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 9 status from ⬜ to ✅ before starting Track 10.
```
