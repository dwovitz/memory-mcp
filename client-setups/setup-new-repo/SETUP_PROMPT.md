# New Repository Setup Prompt

Run this prompt at the start of a new project to capture foundational context
in memory-mcp. Replace `<workspace>` and `<repo>` with actual values.

---

## Prompt

```
You are setting up memory-mcp context for a new repository. Ask the user for
each item below, then store each answer as a memory. Use
workspace="<workspace>" and repo="<repo>" for every call. After all memories
are stored, call get_context_packet to verify setup.

---

### 1. Project intent and audience

Ask: "What is this project for, and who are the primary users or consumers?"

Store as:
  add_memory(
    memory_type="project_fact",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<answer>,
    summary="Project intent and audience",
    tags=["project-intent"],
  )

---

### 2. Technology stack and framework

Ask: "What language, framework, and key libraries will this project use?"

Store as:
  add_memory(
    memory_type="project_fact",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<answer>,
    summary="Technology stack",
    tags=["stack", "tech"],
  )

---

### 3. High-level architecture

Ask: "Describe the high-level architecture: main components, how they
communicate, and any significant design patterns."

Store as:
  add_memory(
    memory_type="architecture_decision",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<answer>,
    summary="High-level architecture",
    tags=["architecture"],
  )

---

### 4. Coding conventions

Ask: "What coding conventions should contributors follow? (naming, formatting,
style, linting rules, etc.)"

Store as:
  add_memory(
    memory_type="coding_preference",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<answer>,
    summary="Coding conventions",
    tags=["conventions", "style"],
  )

---

### 5. Test strategy

Ask: "What is the test strategy? (unit, integration, e2e, coverage
expectations, test runner, CI gate)"

Store as:
  add_memory(
    memory_type="project_fact",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<answer>,
    summary="Test strategy",
    tags=["testing"],
  )

---

### 6. Deployment target

Ask: "Where will this project be deployed? (cloud provider, container
platform, serverless, on-prem, etc.)"

Store as:
  add_memory(
    memory_type="project_fact",
    memory_scope="project",
    workspace="<workspace>",
    repo="<repo>",
    content=<answer>,
    summary="Deployment target",
    tags=["deployment"],
  )

---

### 7. Register repo in workspace

Store a workspace-level memory linking this repo to the workspace:

  add_memory(
    memory_type="project_fact",
    memory_scope="workspace",
    workspace="<workspace>",
    content="Repository <repo> is registered in workspace <workspace>. <one-line description from step 1>",
    summary="Workspace registry: <repo>",
    tags=["registry"],
  )

---

### Verification

Call:
  get_context_packet(
    request="project overview",
    workspace="<workspace>",
    repo="<repo>",
  )

Report context_quality, suggested_next_action, and the fact count to the user.
```
