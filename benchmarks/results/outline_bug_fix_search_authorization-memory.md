# outline_bug_fix_search_authorization memory

## Raw Result

```text
BENCHMARK_RESULT
case_id: outline_bug_fix_search_authorization
project: outline
variant: memory
worktree: D:\git\ai\outline-benchmarks\outline_bug_fix_search_authorization\memory
branch: benchmark/outline_bug_fix_search_authorization-memory
memory_used: yes
memory_context_quality: strong
memory_source_read_policy: implementation_required
memory_source_read_budget_tokens: 4000
sensitive_memory_exposed: no
source_read_budget_obeyed: no
files_inspected_before_edit: plugins/search-postgres/server/PostgresSearchProvider.ts; plugins/search-postgres/server/PostgresSearchProvider.test.ts; server/routes/api/documents/documents.ts; server/routes/api/documents/documents.test.ts; server/routes/api/documents/schema.ts; server/utils/BaseSearchProvider.ts; server/models/Document.ts; server/models/User.ts; server/models/Collection.ts; server/models/Team.ts; server/policies/document.ts; server/policies/collection.ts; server/test/factories.ts; app/scenes/Search/Search.tsx
files_changed: plugins/search-postgres/server/PostgresSearchProvider.ts; plugins/search-postgres/server/PostgresSearchProvider.test.ts; server/routes/api/documents/documents.test.ts
tests_run: corepack yarn test plugins/search-postgres/server/PostgresSearchProvider.test.ts (blocked: provider postgres not registered in isolated run); corepack yarn test server/routes/api/documents/documents.test.ts (blocked: Postgres password authentication failed for user "user"); corepack yarn prettier --check plugins/search-postgres/server/PostgresSearchProvider.ts plugins/search-postgres/server/PostgresSearchProvider.test.ts server/routes/api/documents/documents.test.ts (passed); corepack yarn oxlint plugins/search-postgres/server/PostgresSearchProvider.ts plugins/search-postgres/server/PostgresSearchProvider.test.ts server/routes/api/documents/documents.test.ts (0 errors, existing warnings)
outcome: fixed
notes: Added component project memory noting that Outline search defaults missing/empty statusFilter to Published-only. Dependencies were installed in the fresh worktree with corepack yarn install so checks could run.
```

## Observed UI Metrics

- Runtime: 15m 35s.
- Context window: 118k / 258k tokens used, 46% full.
- Reported changed files: 3.
