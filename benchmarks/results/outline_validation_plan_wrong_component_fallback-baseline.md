# outline_validation_plan_wrong_component_fallback baseline

## Raw Result

```text
BENCHMARK_RESULT
case_id: outline_validation_plan_wrong_component_fallback
project: outline
variant: baseline
worktree: D:\git\ai\outline-benchmarks\outline_validation_plan_wrong_component_fallback\baseline
branch: benchmark/outline_validation_plan_wrong_component_fallback-baseline
memory_used: no
memory_context_quality: n/a
memory_source_read_policy: n/a
memory_source_read_budget_tokens: n/a
files_inspected: docs/ARCHITECTURE.md; package.json; server/routes/api/index.ts; server/routes/api/index.test.ts; server/routes/api/schema.ts; server/routes/api/documents/documents.ts; server/routes/api/documents/schema.ts; server/routes/api/documents/documents.test.ts; server/routes/api/users/users.ts; server/routes/api/users/schema.ts; server/routes/api/users/users.test.ts; server/middlewares/authentication.ts; server/middlewares/authentication.test.ts; server/middlewares/validate.ts; server/middlewares/csrf.ts; server/routes/api/middlewares/apiErrorHandler.ts; server/errors.ts; server/test/support.ts; server/test/TestServer.ts; server/test/factories.ts; shared/helpers/AuthenticationHelper.ts
files_changed: none
tests_or_commands_recommended: yarn test server/routes/api/<resource>/<resource>.test.ts; yarn test server/middlewares/authentication.test.ts; yarn test server/routes/api/index.test.ts; yarn tsc; yarn lint
outcome: Focused validation plan produced without implementation changes.
notes: Did not use stored project memory per baseline prompt. rg was unavailable due access denied, so source inspection used PowerShell Get-ChildItem and Select-String.
```

## Observed UI Metrics

- Context window: 100k / 258k tokens used, 39% full.
- Files changed: none.
