# Product Improvement Prompt: Plan From Benchmark Results

Run this from:

```text
D:\git\ai\memory-mcp
```

You are planning improvements to the `memory-mcp` project based on completed
Outline benchmark results. This is a planning task only. Do not edit code.

First, read these benchmark result files:

```text
benchmarks/results/outline_feature_api_collection_invites-comparison.md
benchmarks/results/outline_bug_fix_search_authorization-comparison.md
benchmarks/results/outline_validation_plan_wrong_component_fallback-comparison.md
benchmarks/results/outline_feature_api_collection_invites-baseline.md
benchmarks/results/outline_feature_api_collection_invites-memory.md
benchmarks/results/outline_bug_fix_search_authorization-baseline.md
benchmarks/results/outline_bug_fix_search_authorization-memory.md
benchmarks/results/outline_validation_plan_wrong_component_fallback-baseline.md
benchmarks/results/outline_validation_plan_wrong_component_fallback-memory.md
```

Then inspect only the `memory-mcp` source and tests needed to understand how to
improve the product. Focus on these likely areas:

- Context packet diagnostics and source-read guidance.
- How `implementation_required`, `focused_snippets`, and token budgets are
  communicated to agents.
- Prompt wording for benchmark memory variants.
- Tests that should prevent future regressions in source-budget compliance,
  sensitive-memory gating, and component fallback.
- Result metrics we should track after the next benchmark run.

Planning goals:

1. Explain what the benchmark results show, including where memory helped,
   where it hurt, and where it was merely neutral.
2. Identify the highest-leverage product changes to improve future benchmark
   outcomes.
3. Propose a concrete implementation plan for `memory-mcp`, ordered by impact
   and risk.
4. Include expected files/modules to change.
5. Include focused tests to add or update.
6. Define measurable success criteria for the next benchmark run.
7. Call out anything that should not be changed yet.

Constraints:

- Do not propose broad rewrites.
- Preserve the behaviors that worked: sensitive memory exclusion and component
  fallback.
- Treat source-read budget noncompliance as the main product failure to address.
- Distinguish product changes from benchmark prompt changes.
- Keep the plan practical enough that another agent can implement it in one
  follow-up task.

End with this exact fenced block:

```text
IMPROVEMENT_PLAN_RESULT
project: memory-mcp
basis: outline benchmark results
top_failure:
top_success:
recommended_changes:
files_to_touch:
tests_to_add_or_update:
next_benchmark_success_criteria:
do_not_change_yet:
open_questions:
```
