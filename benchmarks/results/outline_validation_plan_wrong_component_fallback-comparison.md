# outline_validation_plan_wrong_component_fallback comparison

## Summary

Both variants produced a validation plan without implementation changes.

| Metric | Baseline | Memory |
| --- | --- | --- |
| Context window | 100k / 258k, 39% | 72k / 258k, 28% |
| Memory context quality | n/a | usable |
| Source-read policy | n/a | focused_snippets |
| Source-read budget | n/a | 2000 |
| Source-read budget obeyed | n/a | no |
| Fallback accepted | n/a | yes |
| Files inspected | 21 | 16 |
| Files changed | 0 | 0 |
| Recommended commands | route tests, auth middleware, index test, tsc, lint | route tests, auth middleware, auth helper, API key, OAuth, tsc |

## Observations

- The memory variant used less context and inspected fewer files than baseline.
- The memory fallback behaved as intended by moving from `component=tests` to
  usable project/API/auth context.
- The memory variant still failed the source-read budget target, mainly because
  the fallback/source search path over-read after `rg` was unavailable.
- The baseline plan included API index and lint coverage; the memory plan
  included more auth-scope surfaces such as API keys and OAuth.
