# Definition of Ready

A story is ready for implementation only when it has:

- ID
- title
- priority
- status
- behavior statement
- acceptance criteria
- test plan
- out-of-scope notes
- affected modules/boundaries
- validation command
- done criteria
- dependencies (explicit blockers or "none")
- risk classification
- security review depth

## Size guidance

| Size | Description |
|---|---|
| XS | docs/config/tiny testable change; no migration |
| S | one small behavior change or single module |
| M | one bounded vertical slice; may include migration |
| L | split before coding unless design-only |
| XL | must split; never implement directly |

## Risk classification

| Risk | Examples |
|---|---|
| Low | docs-only, test-only, non-runtime config |
| Standard | normal application logic, new MCP tools |
| High | auth changes, schema migrations, retrieval re-ranking, secrets handling |
| Critical | destructive operations, backup/restore, broad autonomy, multi-user data isolation |
