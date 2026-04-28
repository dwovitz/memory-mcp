# outline_validation_plan_wrong_component_fallback memory

## Raw Result

```text
BENCHMARK_RESULT
case_id: outline_validation_plan_wrong_component_fallback
project: outline
variant: memory
worktree: D:\git\ai\outline-benchmarks\outline_validation_plan_wrong_component_fallback\memory
branch: benchmark/outline_validation_plan_wrong_component_fallback-memory
memory_used: yes
memory_context_quality: usable
memory_source_read_policy: focused_snippets
memory_source_read_budget_tokens: 2000
fallback_accepted: yes
source_read_budget_obeyed: no
files_inspected: server/test/TestServer.ts; server/test/support.ts; server/test/factories.ts; server/middlewares/authentication.ts; server/middlewares/authentication.test.ts; server/routes/api/index.ts; server/routes/api/auth/auth.ts; server/routes/api/auth/auth.test.ts; server/routes/api/apiKeys/apiKeys.ts; server/routes/api/apiKeys/apiKeys.test.ts; server/routes/api/collections/collections.ts; server/routes/api/collections/collections.test.ts; shared/helpers/AuthenticationHelper.ts; shared/helpers/AuthenticationHelper.test.ts; server/models/ApiKey.test.ts; server/models/oauth/OAuthAuthentication.test.ts
files_changed: none
tests_or_commands_recommended: yarn test server/routes/api/<resource>/<resource>.test.ts; yarn test server/middlewares/authentication.test.ts; yarn test shared/helpers/AuthenticationHelper.test.ts; yarn test server/models/ApiKey.test.ts; yarn test server/models/oauth/OAuthAuthentication.test.ts; yarn tsc
outcome: focused validation plan produced; no implementation performed
notes: memory fallback from component=tests to project/api/auth context was accepted; rg was blocked with Access is denied, and one git grep overproduced output, so source_read_budget_obeyed is no
```

## Observed UI Metrics

- Context window: 72k / 258k tokens used, 28% full.
- Files changed: none.
