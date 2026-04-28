# outline_feature_api_collection_invites baseline

## Raw Result

```text
BENCHMARK_RESULT
case_id: outline_feature_api_collection_invites
project: outline
variant: baseline
worktree: D:\git\ai\outline-benchmarks\outline_feature_api_collection_invites\baseline
branch: benchmark/outline_feature_api_collection_invites-baseline
memory_used: no
memory_context_quality: n/a
memory_source_read_policy: n/a
memory_source_read_budget_tokens: n/a
files_inspected_before_edit: server/routes/api/collections/collections.ts; server/routes/api/collections/schema.ts; server/routes/api/collections/collections.test.ts; server/models/UserMembership.ts; server/models/GroupMembership.ts; server/routes/api/users/users.ts; server/routes/api/users/schema.ts; server/commands/userInviter.ts; app/stores/UsersStore.ts; server/test/factories.ts; server/presenters/membership.ts; server/presenters/groupMembership.ts; app/stores/MembershipsStore.ts; app/models/Membership.ts; server/models/User.ts; server/models/Collection.ts; server/policies/collection.ts
files_changed: server/migrations/20260427000000-add-expires-at-to-user-permissions.js; server/models/UserMembership.ts; server/presenters/membership.ts; server/routes/api/collections/schema.ts; server/routes/api/collections/collections.ts; server/models/Collection.ts; server/models/User.ts; server/routes/api/collections/collections.test.ts
tests_run: corepack yarn install --immutable: passed with warnings; corepack yarn prettier --write touched files: passed; corepack yarn test server/routes/api/collections/collections.test.ts: failed, PostgreSQL password authentication failed for user "user"; corepack yarn tsc --noEmit --pretty false: passed; corepack yarn lint:changed: failed, grep/xargs unavailable on Windows shell; corepack yarn oxlint touched TypeScript files: passed with one pre-existing warning in server/models/Collection.ts:523
outcome: implemented optional collection user membership expiresAt support, API presentation, persistence migration, access filtering for expired direct memberships, and focused API tests for create/update/clear/enforcement.
notes: no stored project memory was retrieved or used; dependency install was required because the fresh worktree had no node_modules state.
```

## Observed UI Metrics

- Runtime: 21m 41s.
- Context window: 149k / 258k tokens used, 58% full.
- Reported changed files: 8.
