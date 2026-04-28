# outline_feature_api_collection_invites comparison

## Summary

Both variants completed an implementation and static validation, and both were
blocked from running the focused Jest suite by the same local PostgreSQL
authentication failure.

| Metric | Baseline | Memory |
| --- | --- | --- |
| Runtime | 21m 41s | 22m 54s |
| Context window | 149k / 258k, 58% | 171k / 258k, 66% |
| Memory context quality | n/a | strong |
| Source-read policy | n/a | implementation_required |
| Source-read budget | n/a | 4000 |
| Source-read budget obeyed | n/a | no |
| Files inspected before edit | 17 | 18 |
| Files changed | 8 | 8 |
| Focused Jest | blocked by PostgreSQL auth | blocked by PostgreSQL auth |
| Static typecheck | passed | passed |

## Observations

- The memory variant did not reduce source inspection or context-window usage
  for this case.
- The memory variant implemented a collection-level `inviteExpiration` setting
  on the collection itself, while the baseline implemented membership
  `expiresAt` support. That is a meaningful behavioral divergence to review
  against the intended feature wording.
- The memory packet guidance was correctly classified as strong project context
  with `implementation_required`, but the agent still exceeded the recommended
  source-read budget.
