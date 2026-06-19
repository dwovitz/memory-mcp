# Definition of Done

A story is done only when:

- acceptance criteria are satisfied
- TDD evidence is recorded or exception is justified
- `pytest` passes for the selected validation scope
- Python syntax check passes on changed files
- clean-code review is complete
- security review is complete (scaled by risk)
- docs are updated when behavior or process changes
- no out-of-scope work is included
- handoff is complete and conforms to `docs/workflow/COMPLETION_REPORT.md`
- story status is reconciled across all three controlling backlog files

## TDD evidence

Record:
- `tdd_used`
- `failing_test_observed`
- `reason_if_no_failing_test`
- `tests_added_or_changed`
- `refactor_after_green`

## Clean-code checklist

- small focused units
- clear names, no unnecessary abbreviation
- no speculative abstractions
- no duplicated business logic
- MCP tool layer stays thin (validate → authorize → delegate to service)
- no infrastructure leakage into domain models
- safe error messages (no leaking of sensitive data in exception text)

## Security checklist

- no secrets, credentials, or tokens committed
- no unsafe logging of memory content, workspace names, or user data
- input validation present for all new MCP tool parameters
- secrets guard (`_check_content_for_secrets`) not bypassed
- new auth actions registered appropriately
- migration runs cleanly on empty and seeded databases
- GIN/HNSW index additions have explicit `IF NOT EXISTS` guards
