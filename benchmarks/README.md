# memory-mcp Benchmark Cases

These cases are lightweight product benchmarks for context packet quality. They
use `outline` as the target project and focus on whether retrieved memory helps
an agent do real repository work: feature implementation, bug fixing, and
validation planning.

Run them with the normal test suite:

```powershell
python -m pytest tests/test_benchmark_cases.py
```

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
