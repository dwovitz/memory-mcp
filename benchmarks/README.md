# memory-mcp Benchmark Cases

These cases are lightweight product benchmarks for context packet quality. They
use `outline` as the target project and focus on whether retrieved memory helps
an agent do real repository work: feature implementation, bug fixing, and
validation planning.

Run them with the normal test suite:

```powershell
python -m pytest tests/test_benchmark_cases.py
```

Run automated Outline benchmark prompts with the runner:

```powershell
python benchmarks/run_outline_benchmarks.py --agent-command "<agent command>" --dry-run
python benchmarks/run_outline_benchmarks.py --agent-command "<agent command>" --mode targeted
```

The runner supports three explicit modes:

- `smoke`: cheapest quick check. When `--cases` is omitted, this runs only a
  small representative subset.
- `targeted`: default mode for routine benchmark work. It runs the selected
  cases and variants with conservative token budgets.
- `full`: runs all selected work, but it still honors the suite token budget.

Use `--dry-run` to print the preflight plan without launching agents. The
preflight output includes each case, variant, iteration, mode, estimated prompt
tokens, effective per-case total-token budget, projected suite tokens, and the
allowed/warned/skipped status. If projected suite token use exceeds the active
mode budget, the runner fails before launch unless `--allow-large-token-run` is
present.

Artifacts are compact by default: raw `BENCHMARK_RESULT`, parsed result JSON,
token-budget metrics, and stdout/stderr tails. Pass `--keep-full-artifacts` only
when full prompt and transcript files are needed for debugging.

The benchmark data lives in `cases.json`. Paste-ready agent prompts live in
`prompts/`. Each case defines an Outline user request, synthetic Outline
memories, and expected packet behavior. The tests assert that `memory-mcp`
chooses project context for coding tasks, returns actionable project facts,
avoids unrelated sensitive or personal facts, and recommends source inspection
when implementation is required.

Completed run outputs should be saved under `results/` using one file per
case/variant. Keep the original `BENCHMARK_RESULT` block intact and add any
external notes, such as visible runtime or context-window usage, separately.

These replace the old token-usage prompt set. Token reduction still matters,
but the primary benchmark target is whether the context packet improves the
next coding action rather than merely summarizing stored information.
