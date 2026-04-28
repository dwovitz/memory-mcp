# outline_feature_api_collection_invites memory

## Raw Result

```text
BENCHMARK_RESULT
case_id: outline_feature_api_collection_invites
project: outline
variant: memory
worktree: D:\git\ai\outline-benchmarks\outline_feature_api_collection_invites\memory
branch: benchmark/outline_feature_api_collection_invites-memory
memory_used: yes
memory_context_quality: strong
memory_source_read_policy: implementation_required
memory_source_read_budget_tokens: 4000
source_read_budget_obeyed: no
files_inspected_before_edit: server/routes/api/collections/schema.ts; server/routes/api/collections/collections.ts; server/routes/api/collections/collections.test.ts; server/models/Collection.ts; server/presenters/collection.ts; app/models/Collection.ts; shared/validations.ts; shared/types.ts; app/components/Sharing/Collection/AccessControlList.tsx; app/components/Sharing/Collection/SharePopover.tsx; app/components/Sharing/components/ShareSettingsPopover.tsx; server/routes/api/users/schema.ts; server/routes/api/users/users.ts; server/commands/userInviter.ts; server/commands/userProvisioner.ts; server/models/User.ts; server/migrations/20260319221917-add-collection-template-management.js; server/migrations/20250429130521-add-collection-commenting.js
files_changed: shared/validations.ts; server/routes/api/collections/schema.ts; server/routes/api/collections/collections.ts; server/models/Collection.ts; server/presenters/collection.ts; app/models/Collection.ts; server/migrations/20260427000000-add-collection-invite-expiration.js; server/routes/api/collections/collections.test.ts
tests_run: corepack yarn install --immutable; corepack yarn prettier --check app/models/Collection.ts server/models/Collection.ts server/presenters/collection.ts server/routes/api/collections/collections.test.ts server/routes/api/collections/collections.ts server/routes/api/collections/schema.ts shared/validations.ts server/migrations/20260427000000-add-collection-invite-expiration.js; corepack yarn oxlint app/models/Collection.ts server/models/Collection.ts server/presenters/collection.ts server/routes/api/collections/collections.test.ts server/routes/api/collections/collections.ts server/routes/api/collections/schema.ts shared/validations.ts; corepack yarn tsc --noEmit --pretty false; corepack yarn test server/routes/api/collections/collections.test.ts
outcome: implemented; static checks passed; focused Jest suite blocked by local PostgreSQL password authentication failure for user "user"
notes: Added nullable integer inviteExpiration with 1-365 day API validation, migration, model/client field, presenter output, create/update persistence, and focused route tests. Oxlint reported only pre-existing no-explicit-any warnings in server/models/Collection.ts and server/presenters/collection.ts.
```

## Observed UI Metrics

- Runtime: 22m 54s.
- Context window: 171k / 258k tokens used, 66% full.
- Reported changed files: 8.
