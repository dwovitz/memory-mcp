# Existing Repository Setup Prompt

Run this prompt against an existing repository to ingest its documentation
into memory-mcp. Replace `<workspace>` and `<repo>` with actual values.

---

## Prompt

```
You are ingesting context from an existing repository into memory-mcp. Use
workspace="<workspace>" and repo="<repo>" for every add_memory call. Work
through each source below in order. Skip any file that does not exist.
After ingestion, call get_context_packet to verify context quality.

---

### 1. README.md → project_fact

Read README.md. Store a summary of the project's purpose, audience, and
quick-start information:

  add_memory(
    memory_type="project_fact",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<summary of README>,
    summary="README: project overview",
    tags=["readme", "project-intent"],
  )

---

### 2. Architecture documentation → architecture_decision

Look for docs/ARCHITECTURE.md, ARCHITECTURE.md, docs/architecture/, or
similar. Store the high-level architecture as one memory per major section
or decision:

  add_memory(
    memory_type="architecture_decision",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<section content>,
    summary="Architecture: <section title>",
    tags=["architecture"],
  )

---

### 3. Coding rules → coding_preference

Look for CLAUDE.md, AGENTS.md, GEMINI.md, .cursor/rules/*.mdc, or
.github/copilot-instructions.md. Store the coding conventions and workflow
rules as a single memory (or split by subsystem if large):

  add_memory(
    memory_type="coding_preference",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<rules content>,
    summary="Coding rules from <filename>",
    tags=["conventions", "workflow"],
  )

---

### 4. ADR files → architecture_decision (one per ADR)

Look for docs/adr/, docs/decisions/, or similarly named directories. For
each ADR file found, store one memory:

  add_memory(
    memory_type="architecture_decision",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<ADR content>,
    summary="ADR: <ADR title>",
    tags=["adr"],
  )

---

### 5. Environment and infrastructure → project_fact

Look for .env.example and docker-compose.yml. Store the environment
variable names and service topology. Do NOT store actual secret values:

  add_memory(
    memory_type="project_fact",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<variable names and service names, no secret values>,
    summary="Environment and service topology",
    tags=["env", "infrastructure"],
  )

---

### 6. Top-level source directories → component-scoped project_fact

List the top-level directories under src/, lib/, or the project root that
contain source code. For each significant directory (skip node_modules,
dist, .git, etc.), store one component-scoped memory:

  add_memory(
    memory_type="project_fact",
    memory_scope="component",
    workspace="<workspace>",
    repo="<repo>",
    component=<directory name>,
    content="Component <name>: <one-sentence description of its role>",
    summary="Component: <name>",
    tags=["component", "layout"],
  )

---

### Verification

Call:
  get_context_packet(
    request="project overview and architecture",
    workspace="<workspace>",
    repo="<repo>",
    include_inherited=true,
  )

Report context_quality and suggested_next_action to the user. If
context_quality is "weak", note which sources were missing.
```
