# Implementation Prompt — memory-mcp Quick Wins

Use this prompt to implement the quick-win changes from
`docs/plan/upgrades-for-complex-program-plan.md`. It is written so an AI agent
can execute it cold, without reading the full plan first.

Branch: `feat/complex-program-support`

---

## Prompt

```
We are implementing several quick-win upgrades to memory-mcp as described in
docs/plan/upgrades-for-complex-program-plan.md. The full plan is in that file.
The changes below have been scoped, approved, and are ready to implement.

The working directory is the memory-mcp repo root. The relevant source files
are:
  src/memory_mcp/scopes.py
  src/memory_mcp/mcp_tools/server.py
  docs/ARCHITECTURE.md
  client-setups/README.md
  client-setups/setup-existing-repo/SETUP_PROMPT.md  (new file)
  client-setups/setup-new-repo/SETUP_PROMPT.md       (new file)

Implement all five changes below in order. Run a Python syntax check
(`python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"`)
after step 3.

---

### Change 1 — Add REPO_KEY constant to scopes.py

File: src/memory_mcp/scopes.py

Add a new constant after WORKSPACE_KEY:

    REPO_KEY = "repo"

This is a vocabulary constant. Retrieval does not yet index on repo separately —
that is P0 work in the full plan. Here it is used only to store the value in
applies_to.


### Change 2 — Add `repo` parameter as a project alias across MCP tools

File: src/memory_mcp/mcp_tools/server.py

Affected tools: add_memory, supersede_memory, search_memory, get_context_packet,
list_preferences, summarize_domain_profile.

For each tool:
1. Add `repo: str | None = None` after the `workspace` parameter.
2. Add validation: `repo = _validate_text("repo", repo, max_chars=200)`
   immediately after the workspace validation line.
3. Change the project validation line from:
     project = _validate_text("project", project, max_chars=200)
   to:
     project = _validate_text("project", project, max_chars=200) or repo
   This makes repo an alias: if project is absent, repo fills in as project.

For add_memory and supersede_memory additionally:
4. Import REPO_KEY from memory_mcp.scopes (add to the existing import block).
5. Update _scoped_applies_to to accept `repo: str | None` and store it:
     if repo is not None:
         result[REPO_KEY] = repo
6. Pass `repo=repo` in each _scoped_applies_to(...) call inside add_memory
   and supersede_memory.

Backward compatibility: callers that pass `project` and not `repo` are
unaffected. Existing memories stored without repo still match because retrieval
uses project as the primary key.


### Change 3 — Refuse add_memory for obvious secrets

File: src/memory_mcp/mcp_tools/server.py

1. Add `import re` to the imports at the top of the file.

2. Add the following constant block after the SENSITIVE_TOOLS_ENV line:

    _SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"(AKIA|AGPA|AIDA|AROA|ASCA|ASIA)[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN .{0,20}PRIVATE KEY-----"),
        re.compile(r"[Bb]earer\s+[A-Za-z0-9\-._~+/]{20,}={0,3}"),
        re.compile(r"AccountKey=[A-Za-z0-9+/]{20,}={0,2}"),
    )

3. Add the following helper function (place it near other private helpers,
   after _tags_to_dict):

    def _check_content_for_secrets(content: str) -> None:
        for pattern in _SECRET_PATTERNS:
            if pattern.search(content):
                raise ValueError(
                    "content appears to contain a secret or credential. "
                    "Secrets must not be stored as memories."
                )

4. In add_memory, call _check_content_for_secrets(content) immediately after
   the content validation line (after the _validate_text("content", ...) call).

5. Do the same in supersede_memory.


### Change 4 — Expose search_entities as an MCP tool

File: src/memory_mcp/mcp_tools/server.py

The retrieval service already has HybridRetrievalService.search_entities and
returns list[EntitySearchResult]. Only the MCP wrapper is missing.

1. Import EntitySearchResult from memory_mcp.retrieval (add to the existing
   import that already imports HybridRetrievalService and MemorySearchResult):
     from memory_mcp.retrieval import EntitySearchResult, HybridRetrievalService, MemorySearchResult

2. Add the following MCP tool function just before the run() function:

    @mcp.tool()
    def search_entities(
        query: str | None = None,
        entity_types: list[str] | None = None,
        workspace: str | None = None,
        repo: str | None = None,
        project: str | None = None,
        scope: str | None = None,
        limit: int = 20,
        if_cache_version: str | None = None,
    ) -> dict[str, Any]:
        """Search entities by name, type, or scope."""

        query = _validate_text("query", query, max_chars=2_000)
        workspace = _validate_text("workspace", workspace, max_chars=200)
        repo = _validate_text("repo", repo, max_chars=200)
        project = _validate_text("project", project, max_chars=200) or repo
        entity_types = _validate_string_list("entity_types", entity_types, max_items=25, max_chars=64)
        limit = _bounded_int("limit", limit, minimum=1, maximum=MAX_SEARCH_LIMIT)
        if_cache_version = _validate_cache_version(if_cache_version)
        _authorize_tool_call(
            "search_entities",
            AuthAction.READ,
            workspace=workspace,
            project=project,
        )
        applies_to: dict[str, Any] | None = None
        if workspace or project:
            applies_to = {}
            if workspace:
                applies_to["workspace"] = workspace
            if project:
                applies_to["project"] = project

        with session_scope() as session:
            cache_state = _cache_state_from_session(session)
            if _cache_is_fresh(cache_state, if_cache_version):
                return _cached_response(cache_state)
            retrieval = HybridRetrievalService(session)
            results = retrieval.search_entities(
                text_query=query,
                entity_types=_tuple_or_none(entity_types),
                scope=scope,
                applies_to=applies_to,
                limit=limit,
            )
            return {
                "query": query,
                "workspace": workspace,
                "project": project,
                "entity_types": entity_types,
                "count": len(results),
                "results": [_entity_result_to_dict(result) for result in results],
                "cache": _cache_metadata(cache_state, hit=False),
            }

3. Add the following helper (place it after _tags_to_dict, before
   _check_content_for_secrets):

    def _entity_result_to_dict(result: EntitySearchResult) -> dict[str, Any]:
        entity = result.entity
        return {
            "id": str(entity.id),
            "entity_type": entity.entity_type,
            "name": entity.name,
            "aliases": entity.aliases or [],
            "attributes": entity.attributes or {},
            "applies_to": entity.applies_to or {},
            "rank_score": result.rank_score,
        }


### Change 5 — Docs and setup prompts

**5a. Update docs/ARCHITECTURE.md**

In the "MCP Tool Surface" table, add two rows:
  - `search_entities` | Search named entities by text query, type, workspace, or repo.
  - `get_memory_cache_state` | Return a version token for cache validation.

After the scope_path diagram in the "Scope Hierarchy" section, add:

#### `repo` parameter

Write tools (add_memory, supersede_memory) and read tools (search_memory,
get_context_packet, list_preferences, summarize_domain_profile) all accept a
`repo` parameter. When `repo` is provided and `project` is omitted, the server
treats them as equivalent — so callers in a multi-repo workspace can use `repo`
as the natural vocabulary without changing retrieval behavior.

The `repo` value is also stored in `applies_to.repo` for future index support.

#### Canonical `scope_path` prefixes

When the classic four-layer hierarchy is not enough, use `scope_path` with
these canonical prefixes so that different clients stay consistent:

| Prefix | Example | Meaning |
| --- | --- | --- |
| `workspace:` | `workspace:mycompany` | Top-level workspace |
| `repo:` | `repo:my-service` | Git repository |
| `project:` | `project:my-service` | Logical project (often same as repo) |
| `component:` | `component:api` | Subsystem within a project |
| `topic:` | `topic:auth` | Subject area within a component |
| `branch:` | `branch:main` | Branch-local truth |
| `feature:` | `feature:dark-mode` | In-progress feature context |

Example: a component-level fact scoped to a specific branch:
  scope_path=["workspace:mycompany", "repo:my-service", "component:api", "branch:feat-x"]

**5b. Update client-setups/README.md**

Add a "Setup Prompts" section near the top that references:
- client-setups/setup-new-repo/SETUP_PROMPT.md
- client-setups/setup-existing-repo/SETUP_PROMPT.md

Update step 3 of the Install Pattern to use `repo=` instead of `project=` as
the primary vocabulary example.

**5c. Create client-setups/setup-new-repo/SETUP_PROMPT.md**

A prompt template an agent runs at the start of a new project to capture:
- Project intent and audience
- Technology stack and framework
- High-level architecture
- Coding conventions
- Test strategy
- Deployment target
- A workspace-level memory registering the repo in the workspace

Each answer should be stored as a memory with the appropriate memory_type
(project_fact, architecture_decision, coding_preference) and
memory_scope="project", workspace="<workspace>", repo="<repo>".

End with a get_context_packet call to verify the setup.

**5d. Create client-setups/setup-existing-repo/SETUP_PROMPT.md**

A prompt template an agent runs against an existing repo to ingest:
- README.md → project_fact
- docs/ARCHITECTURE.md or similar → architecture_decision
- CLAUDE.md / .cursor/rules/*.mdc / copilot-instructions.md → coding_preference
- ADR files → architecture_decision (one per ADR)
- .env.example / docker-compose.yml → project_fact (no actual secret values)
- Top-level source directories → component-scoped project_fact entries

End with a get_context_packet call to verify context_quality.

---

After all changes, run a Python syntax check on server.py. If tests are
available (`pytest`), run them. Report any failures.
```
