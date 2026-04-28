# outline_bug_fix_search_authorization baseline

## Raw Result

```text
BENCHMARK_RESULT
case_id: outline_bug_fix_search_authorization
project: outline
variant: baseline
worktree: D:\git\ai\outline-benchmarks\outline_bug_fix_search_authorization\baseline
branch: benchmark/outline_bug_fix_search_authorization-baseline
memory_used: no
memory_context_quality: n/a
memory_source_read_policy: n/a
memory_source_read_budget_tokens: n/a
files_inspected_before_edit: benchmarks/prompts/02a-baseline-outline-bugfix-search-private-title-leak.md; server/routes/api/documents/documents.ts; server/routes/api/documents/documents.test.ts; server/utils/BaseSearchProvider.ts; server/utils/SearchProviderManager.ts; server/utils/opensearch.ts; plugins/search-postgres/server/PostgresSearchProvider.ts; plugins/search-postgres/server/PostgresSearchProvider.test.ts; server/policies/document.ts; server/models/Document.ts; server/test/factories.ts; server/models/Collection.ts; server/models/Document.test.ts; server/models/User.ts; server/models/Team.ts
files_changed: plugins/search-postgres/server/PostgresSearchProvider.ts; server/routes/api/documents/documents.test.ts
tests_run: corepack yarn prettier --write plugins/search-postgres/server/PostgresSearchProvider.ts server/routes/api/documents/documents.test.ts; corepack yarn test server/routes/api/documents/documents.test.ts -t "another user's draft" (failed: PostgreSQL password authentication failed for user "user"); corepack yarn oxlint --type-aware plugins/search-postgres/server/PostgresSearchProvider.ts server/routes/api/documents/documents.test.ts; git diff --check
outcome: Fixed default search authorization leak for drafts; added regression coverage for documents.search_titles and documents.search.
notes: yarn was unavailable directly, so Corepack Yarn was used. Dependencies were installed in the benchmark worktree. Oxlint exited 0 with existing no-explicit-any warnings in touched files. Jest could not complete because the local test database credentials are not valid in this environment.
```

## Observed UI Metrics

- Not recorded. The supplied screenshot appears to show the memory variant result.
