# Context Packet Synthesis Examples

These examples use the synthetic seed data. Token counts are approximate
character-based estimates from the synthesis service, not tokenizer-specific
counts.

## Example 1: Project Request

Request:

```text
What should I remember while working on the memory-mcp Python project?
```

Relevant domains:

- Included: project facts, app knowledge, coding preferences.
- Excluded: medication, entertainment, devices unrelated to development,
  archived memories.

Before synthesis, raw memory context might include full content, summaries,
evidence JSON, metadata JSON, applies-to scopes, and lifecycle fields:

```text
project_fact
memory-mcp is a local-first personal memory MCP server using Python,
PostgreSQL, Docker, and pgvector.
summary: memory-mcp architecture fact.
evidence: [{"kind": "explicit", "text": "...", "source": "..."}]
metadata: {"seed": true, "synthetic": true, "category": "project", ...}
applies_to: {"project": "memory-mcp"}

app_knowledge
Codex is used as the local coding assistant while building the memory-mcp
project.
...

coding_preference
Alex prefers small, modular Python changes with clear summaries and no
overbuilding.
...
```

Approximate before tokens: `215`

Synthesized packet:

```text
# Context Packet
Request domain: project

## Preferences
- Current coding preference.

## Facts
- memory-mcp architecture fact.
- Codex app usage.

## Token Estimate
Before: 215
After: 46
Reduction: 78.6%
```

## Example 2: Entertainment Request With Evidence

Request:

```text
What kind of shows does Alex like, and why?
```

Relevant domains:

- Included: entertainment preferences and inferred entertainment preferences.
- Excluded: medications, project facts, coding preferences, app facts.
- Detail included because the request asks "why".
- Evidence included only when requested by the caller.

Synthesized packet:

```text
# Context Packet
Request domain: entertainment

## Preferences
- Likes Severance. Detail: Alex likes Severance for its mystery, workplace
  satire, and controlled sci-fi tone.
- Inferred sci-fi preference. Detail: Alex likely prefers character-driven
  sci-fi with mystery over bleak survival horror.

## Evidence
- entertainment_preference: explicit: Seed scenario says Alex liked Severance.
- inferred_preference: inference: Inferred from liking Severance and disliking
  a bleak zombie show.

## Token Estimate
Before: 190
After: 91
Reduction: 52.1%
```
