# Implementation Prompt — Track 1R Auto-Capture + Distillation Verification/Repair

**Model:** Sonnet
**Estimated effort:** 1–3 hrs if mostly verification; 1 day if repair is required
**Branch:** `fix/track-1-auto-capture-verification`

## Context

`docs/prompts/ROADMAP.md` currently marks Track 1 — Auto-capture + distillation — as complete, but direct checks on `main` found multiple expected Track 1 artifacts missing.

The original Track 1 prompt is:

- `docs/prompts/impl-auto-capture.md`

The full implementation plan referenced by Track 1 is:

- `docs/superpowers/plans/2026-05-07-auto-capture-distillation.md`

This repair track must verify whether Track 1 is actually complete, restore missing implementation/documentation if it is not, or correct the roadmap/prompt files if the implementation was intentionally superseded by a different design.

## Do not continue later tracks first

Do not start Track 7 or later until this repair track is resolved. The roadmap should not claim Track 1 is complete unless its implementation artifacts and verification commands match the accepted design.

## Step 1: Create branch

```bash
git checkout main
git pull origin main
git checkout -b fix/track-1-auto-capture-verification
```

## Step 2: Read source documents

Read these files in full:

```text
docs/prompts/ROADMAP.md
docs/prompts/impl-auto-capture.md
docs/superpowers/plans/2026-05-07-auto-capture-distillation.md
```

## Step 3: Audit expected Track 1 artifacts

Compare `docs/prompts/impl-auto-capture.md` against the current repository.

Expected created files from the prompt:

```text
migrations/versions/0010_staging_observations.py
src/memory_mcp/models/staging.py
src/memory_mcp/repositories/staging.py
src/memory_mcp/distiller/__init__.py
src/memory_mcp/distiller/router.py
src/memory_mcp/distiller/prompts.py
src/memory_mcp/distiller/service.py
src/memory_mcp/distiller/runner.py
hooks/post_tool_use.py
hooks/user_prompt_submit.py
hooks/session_start.py
hooks/session_end.py
hooks/_client.py
tests/test_staging_repository.py
tests/distiller/test_router.py
tests/distiller/test_service.py
tests/hooks/test_post_tool_use.py
tests/hooks/test_user_prompt_submit.py
docs/auto_capture.md
```

Expected modified files from the prompt:

```text
src/memory_mcp/mcp_tools/server.py
docker-compose.yml
pyproject.toml
README.md
src/memory_mcp/models/__init__.py
```

Specific expected behavior:

- MCP tool `enqueue_observation`
- MCP tool `get_memory_by_id`
- Postgres-backed staging observations table/model/repository
- background distiller service/runner
- hook client and Claude Code hook scripts
- `distiller` service in `docker-compose.yml`
- `anthropic` dependency in `pyproject.toml`
- README link to `docs/auto_capture.md`
- docs explaining auto-capture setup and behavior

## Step 4: Decide actual state

Classify the result as one of these:

### Case A — Track 1 is incomplete

Missing artifacts are required and must be implemented. Implement the missing pieces using `docs/superpowers/plans/2026-05-07-auto-capture-distillation.md` as the controlling plan.

### Case B — Track 1 was intentionally superseded

The repo uses a different accepted design. In this case, update:

- `docs/prompts/impl-auto-capture.md`
- `docs/prompts/ROADMAP.md`
- relevant README/docs

so the source-of-truth documents match the implemented design. Do not leave stale file lists or false completion criteria.

### Case C — Track 1 exists under renamed paths

Update the prompt and docs to point to the actual files, and add compatibility notes if the old names are misleading.

## Step 5: Repair if required

If Case A applies, implement only the missing Track 1 scope. Do not expand into Track 7+.

Follow the original verification guidance where possible:

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_staging_repository.py tests/distiller/ tests/hooks/ -v
alembic upgrade head
```

If test paths differ because the accepted design changed, update the verification commands in the docs and explain why.

## Step 6: Add an audit note

Create or update a short audit note documenting the result:

```text
docs/prompts/track-1r-auto-capture-audit.md
```

Include:

- files checked
- missing files found
- decision: Case A/B/C
- files repaired or docs corrected
- verification commands run
- remaining risk, if any

## Step 7: Update ROADMAP

Update `docs/prompts/ROADMAP.md` so Track 1R is marked complete after this work merges.

If Track 1 remains incomplete after the repair branch, mark Track 1 as not complete or add a clear warning before the remaining tracks.

## Step 8: Commit, merge, push

```bash
git add .
git commit -m "fix: verify and repair Track 1 auto-capture roadmap state"
git checkout main
git merge fix/track-1-auto-capture-verification --no-ff -m "fix: verify Track 1 auto-capture completion"
git push origin main
```

## Handoff prompt after completion

If Track 1 is verified/repaired and merged:

```text
Continue memory-mcp roadmap. Track 1R (auto-capture verification/repair) is complete and merged to main.
Next: read docs/prompts/ROADMAP.md and continue with the first remaining incomplete track after Track 1R. Do not skip sequencing constraints.
If Track 7 is next, read docs/prompts/impl-p2-event-flow.md and implement it on branch feat/p2-event-flow using Sonnet.
```
