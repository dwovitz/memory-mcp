# Product Improvement Prompt: Token-Budgeted Benchmark Runs

Run this from:

```text
D:\git\ai\memory-mcp
```

Implement benchmark-runner safeguards so a single Outline benchmark run cannot
consume an unbounded amount of model context or token budget.

Goal:
Enhance the existing benchmark automation with explicit run modes, token
preflight, actual token-use reporting, hard per-case budget stops, and compact
artifacts. The default benchmark path should be cheap enough for routine
iteration, while full benchmark runs remain available only when explicitly
requested.

Context:

- Benchmark cases live in:

```text
benchmarks/cases.json
```

- The CLI entry point is:

```text
benchmarks/run_outline_benchmarks.py
```

- The runner implementation is:

```text
benchmarks/outline_benchmark_runner.py
```

- Existing tests cover the runner and benchmark case contracts:

```text
tests/test_outline_benchmark_runner.py
tests/test_benchmark_cases.py
```

- Benchmark result artifacts currently preserve `BENCHMARK_RESULT` blocks under:

```text
benchmarks/results/
```

Use `rg` for discovery first. It should be available in this environment now.
Keep source inspection bounded: enumerate likely paths, read only small snippets
from the directly implicated files, then edit.

Product changes to implement:

1. Add benchmark run modes.

   Add a first-class run mode concept with these modes:

   - `smoke`: cheapest useful run for quick iteration.
   - `targeted`: default mode for normal benchmark work.
   - `full`: all selected cases and variants, intended for explicit use only.

   The CLI should accept:

```text
--mode smoke|targeted|full
```

   Default to `targeted`. Keep existing `--cases`, `--variants`, and
   `--iterations` behavior backward-compatible.

   Suggested semantics:

   - `smoke`: limit to a small representative subset unless the user provides
     explicit `--cases`.
   - `targeted`: run the normal selected cases, but enforce conservative token
     budgets.
   - `full`: run all selected work and require an explicit flag when projected
     token use is large.

2. Add token budget profiles.

   Define budget settings in a structured place that tests can inspect. This can
   be in code or in `cases.json`, but keep the shape stable and simple.

   Each active run should have effective budget values for:

```text
max_prompt_tokens
max_completion_tokens
max_total_tokens
max_total_run_tokens
max_source_files_before_edit
max_snippets_before_edit
```

   Budget values may be mode defaults, with optional per-case overrides. Avoid
   requiring every existing case to repeat identical budget data.

3. Add preflight token estimation.

   Before launching agents, estimate prompt tokens for each planned run and the
   whole suite. The estimator does not need provider-perfect tokenization; a
   deterministic conservative approximation is acceptable.

   Preflight output should show:

```text
case id
variant
iteration
mode
estimated prompt tokens
effective per-case total-token budget
projected suite token budget
whether the run is allowed, warned, or skipped
```

   Add a dry-run/preflight path that does not launch agents and prints this
   plan. Reuse `--dry-run` if that keeps the CLI smaller.

4. Add explicit large-run opt-in.

   Add:

```text
--allow-large-token-run
```

   If projected suite token use exceeds the mode's `max_total_run_tokens`, the
   runner should fail before launching agents unless this flag is present.

   `full` mode should be allowed, but it should not silently bypass the suite
   budget.

5. Track actual token usage when available.

   Parse actual usage from agent output when the provider or wrapper exposes it.
   Do not make the whole runner depend on one provider-specific format.

   Store these fields in run summaries when known:

```text
estimated_prompt_tokens
actual_input_tokens
actual_output_tokens
actual_total_tokens
token_budget_obeyed
token_budget_exception
```

   If actual usage is unavailable, summaries should say `unknown`, not guess.

6. Add hard per-case budget stops.

   If a planned case is over budget before launch, mark it skipped with a clear
   reason unless the user explicitly allowed large runs.

   If actual usage is parsed after completion and exceeds the per-case budget,
   mark that result as budget failed:

```text
token_budget_obeyed: no
token_budget_exception: <short reason>
```

   Do not let one over-budget case erase the rest of the suite summary. The
   runner should report the failure cleanly.

7. Compact default artifacts.

   By default, save compact artifacts:

   - raw `BENCHMARK_RESULT` block
   - parsed fields
   - summary metadata
   - token-budget metrics
   - concise stdout/stderr tail if useful for debugging failures

   Add:

```text
--keep-full-artifacts
```

   When set, preserve the current full transcript behavior. When unset, avoid
   writing large raw transcripts that make future analysis token-heavy.

8. Keep paired benchmark comparison cheap.

   Preserve baseline and memory variants, but make summaries compare compact
   scorecards instead of requiring agents or humans to keep both full transcripts
   in active context.

   The Markdown summary should include a compact table with:

```text
case
variant
status
estimated_prompt_tokens
actual_total_tokens
token_budget_obeyed
source_read_budget_obeyed
result artifact path
```

9. Tests.

   Add focused tests for:

   - mode selection defaults to `targeted`.
   - `smoke` reduces the planned run set when cases are not explicitly provided.
   - preflight reports estimated tokens without launching the agent.
   - suite budget overflow fails before launch unless
     `--allow-large-token-run` is passed.
   - summary JSON and Markdown include token-budget fields.
   - compact artifacts omit full transcripts by default.
   - `--keep-full-artifacts` preserves full transcript output.

Constraints:

- Preserve existing benchmark case IDs and prompt paths.
- Preserve current `BENCHMARK_RESULT` parsing.
- Keep existing tests passing unless their expectations need a targeted update
  for the new default artifact behavior.
- Do not introduce a provider-specific tokenizer dependency just for preflight.
- Do not store secrets or provider raw telemetry in artifacts.
- Keep CLI behavior explicit and documented in `benchmarks/README.md`.

Verification:

Run the focused benchmark tests first:

```powershell
python -m pytest tests/test_outline_benchmark_runner.py tests/test_benchmark_cases.py
```

Then run any broader relevant tests if the change touches shared code.

Final response requirements:

Include:

- files changed
- tests run
- a concise note on the default run mode and large-run guard
- any known limitation of token usage parsing
