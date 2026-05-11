# Implementation Prompt — Auto-Capture + Distillation

**Model:** Sonnet
**Estimated effort:** 1–2 days
**Branch:** `feat/auto-capture-distillation`

## Context

Adds hook-driven auto-capture of Claude Code session events into a Postgres-backed
staging queue, with a background distiller that compresses raw observations into
typed scoped memories using model-routed Claude calls. Surfaces compressed context
automatically on UserPromptSubmit.

The complete implementation plan already exists:
`docs/superpowers/plans/2026-05-07-auto-capture-distillation.md`

## Instructions

1. Read `docs/superpowers/plans/2026-05-07-auto-capture-distillation.md` in full.
2. Use `superpowers:subagent-driven-development` or `superpowers:executing-plans`
   to implement it task-by-task exactly as written.
3. Run `pytest` after each task. Fix failures before moving on.
4. Run `alembic upgrade head` after the migration task.

## Key files (from the plan)

**Create:**
- `migrations/versions/0010_staging_observations.py`
- `src/memory_mcp/models/staging.py`
- `src/memory_mcp/repositories/staging.py`
- `src/memory_mcp/distiller/__init__.py`
- `src/memory_mcp/distiller/router.py`
- `src/memory_mcp/distiller/prompts.py`
- `src/memory_mcp/distiller/service.py`
- `src/memory_mcp/distiller/runner.py`
- `hooks/post_tool_use.py`
- `hooks/user_prompt_submit.py`
- `hooks/session_start.py`
- `hooks/session_end.py`
- `hooks/_client.py`
- `tests/test_staging_repository.py`
- `tests/distiller/test_router.py`
- `tests/distiller/test_service.py`
- `tests/hooks/test_post_tool_use.py`
- `tests/hooks/test_user_prompt_submit.py`
- `docs/auto_capture.md`

**Modify:**
- `src/memory_mcp/mcp_tools/server.py` — add `enqueue_observation`, `get_memory_by_id`
- `src/memory_mcp/models/__init__.py` — export `StagingObservation`
- `docker-compose.yml` — add `distiller` service
- `pyproject.toml` — add `anthropic` dependency
- `README.md` — link to `docs/auto_capture.md`

## Verification

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_staging_repository.py tests/distiller/ tests/hooks/ -v
alembic upgrade head
```

## Merge

```bash
git checkout main
git merge feat/auto-capture-distillation --no-ff -m "feat: add auto-capture and distillation pipeline"
git push origin main
```

## Handoff prompt for Track 2

```
Continue memory-mcp roadmap. Track 1 (auto-capture + distillation) is complete and merged to main.
Next: Track 2 — read docs/prompts/impl-semantic-retrieval.md and implement it.
Branch off main as feat/p0-semantic-retrieval. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 1 status from ⬜ to ✅ before starting Track 2.
```
