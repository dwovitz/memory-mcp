# Claude Code

Read `AGENTS.md` first; it is canonical.

Bias toward architecture, planning, ambiguity detection, and independent review. Use canonical
repository sources rather than duplicating shared policy. On conflict, `AGENTS.md` and accepted
repo-local decisions win over this wrapper.

<!-- secret-migrate:start -->
## Local secret management

Read `docs/secret-management.md` before running this repository. Use the generated `scripts/with-secrets` or `scripts/dev-up` launcher, and never
inspect or print secret values.
<!-- secret-migrate:end -->

<!-- ai-rules:start -->
Shared always-on policy is authored once in `ai-rules` and installed from there.
Read it at `/home/dwovitz/src/ai/ai-rules/rules/` — core, workflow, memory, routing, safety.

Do not copy shared policy into this file. Repo-specific rules are canonical in
`AGENTS.md` and win on conflict.
<!-- ai-rules:end -->
