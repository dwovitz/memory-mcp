# Track 1R Audit — Auto-Capture + Distillation

**Date:** 2026-05-11
**Branch:** `fix/track-1-auto-capture-verification`
**Verdict:** Case A — Track 1 was incomplete; all artifacts repaired.

## Files Checked

### Expected but MISSING (19 files)

```
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

### Expected modified files — status at audit time

- `src/memory_mcp/mcp_tools/server.py` — existed, missing `enqueue_observation` / `get_memory_by_id`
- `src/memory_mcp/models/__init__.py` — existed, missing `StagingObservation` export
- `docker-compose.yml` — existed, missing `distiller` service
- `pyproject.toml` — existed, missing `anthropic>=0.40` dependency
- `README.md` — existed, missing link to `docs/auto_capture.md`

## Decision

**Case A — Track 1 is incomplete.** The `feat/auto-capture-distillation` branch was
marked ✅ in the roadmap but the implementation was never merged to main. All 19
expected files were missing and all 5 expected file modifications were absent.

## Files Repaired / Created

Created all 19 missing files. Modified all 5 expected files.

Additional fixes applied vs. original plan:
- `down_revision` in migration set to `"0007_code_citations"` (actual alembic head).
- `DistillerService._normalize` restructures `ingest_key` into `metadata.ingest_key`
  to match `IngestWriter.upsert_memories` contract (plan had a mismatch).
- `StagingRepository.claim_batch` / `mark_done` / `mark_failed` use
  `synchronize_session=False` + `expire_all()` to avoid SQLAlchemy ORM identity-map
  races with bulk updates.
- Removed `tests/distiller/__init__.py` and `tests/hooks/__init__.py` to prevent
  pytest from shadowing the top-level `hooks` source package with the test
  subdirectory of the same name.
- Added `autouse` cleanup fixture in `tests/test_staging_repository.py` for test
  isolation against a shared Postgres instance.
- Added root `conftest.py` and `pyproject.toml` pythonpath `"."` for `hooks` import.

## Verification Commands Run

```
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
# → parses OK

alembic upgrade head
# → Running upgrade 0007_code_citations -> 0010_staging_observations

pytest tests/test_staging_repository.py tests/distiller/ tests/hooks/ -v
# → 10 passed

pytest tests/test_mcp_tools.py -v
# → 26 passed (no regressions)
```

## Remaining Risk

- `distiller/runner.py` and `docker-compose.yml` distiller service cannot be smoke-
  tested without a live `ANTHROPIC_API_KEY` and a running Docker stack. The runner
  unit test (`tests/distiller/test_runner_smoke.py` from the original plan) was not
  included — add it in a follow-up if end-to-end distiller validation is needed.
- The `hooks` package requires Python to be run from the project root or with
  the project root on `PYTHONPATH`; this is documented in `docs/auto_capture.md`.
