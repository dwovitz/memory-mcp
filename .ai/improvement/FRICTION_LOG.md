# Friction Log

Append-only log of workflow friction observed during story execution.

## What to log

Log only signals a future self-improvement scan can act on:

- a step that had to be redone (failed review, failed validation, rejected output, scope correction)
- a routing decision that turned out wrong (wrong model, wrong effort, missing escalation)
- a context retrieval that was over- or under-scoped
- a missing skill or tool that would have prevented work
- a template or prompt field that was unclear, redundant, or routinely left blank
- a recurring manual step that should be automated
- a successful non-obvious approach worth promoting to a rule

Do not log routine completions, one-off typos, or speculation without evidence.

## Entry format

```markdown
### YYYY-MM-DD — <STORY_ID or task key> — <one-line summary>

- handoff: `.ai/handoffs/<file>.md`
- category: redo | routing | context | missing-tool | template | recurring-manual | validated-pattern
- target: skill | agent | prompt | routing | template | workflow | other
- observation: <what happened, concrete>
- evidence: <handoff section, commit, file path, or quote>
- proposed direction: <one-line idea>
- scan status: open
```

When a self-improvement scan consumes an entry, set `scan status: consumed-<scan-date>` and reference the proposal file. Entries are never deleted.

## Scan triggers

A self-improvement scan runs when either condition holds:
- five consumable entries have accumulated since the last scan, or
- any entry with `category: redo` or `category: routing` is appended.

## Entries

<!-- No entries yet — log begins here -->
