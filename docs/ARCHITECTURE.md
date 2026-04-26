# Architecture

## Overview

`memory-mcp` is a local Python MCP stdio server backed by PostgreSQL. It stores
structured memories and exposes tools that retrieve compact, task-specific
context for coding agents.

```mermaid
flowchart LR
    Agent["MCP-capable agent"]
    Server["memory-mcp stdio server"]
    Service["Application services"]
    Retrieval["Hybrid retrieval"]
    DB["PostgreSQL + pgvector"]

    Agent <-->|MCP stdio tools| Server
    Server --> Service
    Server --> Retrieval
    Service --> DB
    Retrieval --> DB
```

## Runtime Components

```mermaid
flowchart TB
    CLI["memory-mcp command"]
    Main["memory_mcp.main"]
    MCP["mcp_tools.server"]
    DBSession["db.session_scope"]
    MemoryService["MemoryService"]
    RetrievalService["HybridRetrievalService"]
    ContextService["ContextSynthesisService"]
    PruningService["PruningService"]
    Repositories["Repositories"]
    Models["SQLAlchemy models"]
    Postgres["PostgreSQL"]

    CLI --> Main --> MCP
    MCP --> DBSession
    DBSession --> MemoryService
    DBSession --> RetrievalService
    DBSession --> ContextService
    DBSession --> PruningService
    MemoryService --> Repositories
    Repositories --> Models --> Postgres
    RetrievalService --> Models
    ContextService --> RetrievalService
    PruningService --> Repositories
```

## Storage Model

The database keeps durable context as lifecycle-aware rows. Most tables include
confidence, sensitivity, status, and `applies_to` scope metadata.

```mermaid
erDiagram
    ENTITIES ||--o{ MEMORIES : "describes"
    ENTITIES ||--o{ RELATIONSHIPS : "source"
    ENTITIES ||--o{ RELATIONSHIPS : "target"
    MEMORIES ||--o{ MEMORY_TAGS : "tagged by"
    RETRIEVAL_PROFILES ||--o{ CONTEXT_PACKETS : "configures"
    CONTEXT_PACKETS ||--o{ CONTEXT_PACKET_MEMORIES : "contains"
    MEMORIES ||--o{ CONTEXT_PACKET_MEMORIES : "source"
    MEMORIES ||--o{ PRUNING_LOG : "audited by"

    ENTITIES {
        uuid id PK
        string entity_type
        string name
        jsonb aliases
        jsonb attributes
        jsonb applies_to
    }

    MEMORIES {
        uuid id PK
        uuid entity_id FK
        string memory_type
        text content
        text summary
        jsonb evidence
        jsonb metadata
        vector embedding
        string status
        string sensitivity
        numeric confidence
        jsonb applies_to
    }

    MEMORY_TAGS {
        uuid id PK
        uuid memory_id FK
        string tag
        string status
    }

    RELATIONSHIPS {
        uuid id PK
        uuid source_entity_id FK
        uuid target_entity_id FK
        string relationship_type
        text description
    }

    CONTEXT_PACKETS {
        uuid id PK
        uuid retrieval_profile_id FK
        string title
        text content
        int token_estimate
    }

    PRUNING_LOG {
        uuid id PK
        uuid memory_id FK
        string action
        text reason
        jsonb before_state
        jsonb after_state
    }
```

## MCP Tool Surface

| Tool | Purpose |
| --- | --- |
| `add_memory` | Store a new memory with optional scope, tags, evidence, and lifecycle metadata. |
| `archive_memory` | Mark a memory archived. |
| `supersede_memory` | Replace an outdated memory while preserving lineage. |
| `search_memory` | Search memories using structured filters, text, tags, scope, and sensitivity controls. |
| `get_context_packet` | Generate a compact LLM-ready packet for a task. |
| `list_preferences` | Retrieve preference memories by domain and scope. |
| `list_liked_media` | Retrieve liked entertainment preferences. |
| `list_disliked_media` | Retrieve disliked entertainment preferences. |
| `list_medications_for_person` | Retrieve medication memories for an explicit person ID. |
| `summarize_domain_profile` | Summarize a domain as a bounded context packet. |
| `run_pruning_pass` | Archive, supersede, compress, and decay memory according to pruning rules. |

## Retrieval Flow

```mermaid
flowchart TD
    Request["Agent request"]
    Classify["Classify domain and memory types"]
    Scope{"Scope supplied?"}
    ScopePath["Search scope_path layers"]
    Hierarchy["Search component -> project -> workspace -> global"]
    Flat["Search direct filters"]
    Rank["Rank by text, confidence, and recency"]
    Budget["Apply result and token budgets"]
    Packet["Render context packet"]

    Request --> Classify --> Scope
    Scope -->|"scope_path"| ScopePath --> Rank
    Scope -->|"workspace/project/component"| Hierarchy --> Rank
    Scope -->|"none"| Flat --> Rank
    Rank --> Budget --> Packet
```

Ranking combines:

- PostgreSQL full-text rank across memory content and summary.
- Confidence score.
- Recency score.
- Structured filters for memory type, status, sensitivity, tags, `applies_to`,
  scope, and minimum confidence.

Vector search is scaffolded only. The `memories.embedding` column and pgvector
extension are available, but embedding generation and HNSW indexing are deferred
until a fixed embedding model and dimension are selected.

## Scope Hierarchy

Classic hierarchy fields are stored in `applies_to`:

```mermaid
flowchart BT
    Component["component memory"]
    Project["project memory"]
    Workspace["workspace memory"]
    Global["global memory"]

    Component --> Project --> Workspace --> Global
```

Use these scopes when the project, component, and workspace are enough:

- `memory_scope="global"`
- `memory_scope="workspace"` plus `workspace`
- `memory_scope="project"` plus `project`
- `memory_scope="component"` plus `project` and `component`

Use `scope_path` when context needs more layers, such as repo, app, module,
branch, feature, or session.

```mermaid
flowchart LR
    G["global"]
    U["user"]
    D["domain"]
    P["project"]
    R["repo"]
    A["app"]
    M["module"]
    B["branch"]
    F["feature"]

    G --> U --> D --> P --> R --> A --> M --> B --> F
```

When `include_inherited=true`, retrieval walks from the direct scope back
toward the root. Lower scopes can hide parent facts with
`overrides_memory_ids`, allowing branch-local truth without corrupting main
branch memory.

## Context Packet Synthesis

`ContextSynthesisService` turns retrieval results into a compact packet:

```mermaid
flowchart LR
    Memories["Ranked memories"]
    Split["Preference/fact/episodic buckets"]
    Summaries["Prefer summaries"]
    Evidence{"Evidence requested?"}
    Render["Markdown packet"]
    Estimate["Before/after token estimate"]

    Memories --> Split --> Summaries --> Evidence
    Evidence -->|"yes"| Render
    Evidence -->|"no"| Render
    Render --> Estimate
```

The packet includes:

- Request classification.
- Preferences.
- Facts.
- Episodic context.
- Optional evidence.
- Raw-context token estimate.
- Rendered-packet token estimate.
- Reduction percentage.

## Lifecycle

```mermaid
stateDiagram-v2
    [*] --> active
    active --> archived: no longer useful
    active --> superseded: replaced by newer fact
    active --> deleted: intentional logical deletion
    archived --> [*]
    superseded --> [*]
    deleted --> [*]
```

Lifecycle rules:

- Active memory is eligible for normal retrieval.
- Archived memory is preserved but hidden from normal context.
- Superseded memory is preserved for lineage and audit.
- Deleted is a logical status, not a physical purge.
- Pruning writes decisions to `pruning_log`.

## Safety Boundaries

- The server is designed for trusted local stdio clients.
- Default retrieval includes only `normal` sensitivity memory.
- `MEMORY_MCP_ENABLE_MUTATION_TOOLS=true` is required for MCP write, archive,
  supersede, and pruning tools.
- `MEMORY_MCP_ENABLE_SENSITIVE_TOOLS=true` plus `include_sensitive=true` is
  required for sensitive and private reads.
- Evidence is omitted by default in most tools.
- Write tools return minimal metadata by default and require explicit
  `include_content` or `include_evidence` echo.
- Text, JSON payloads, tag counts, result counts, scope paths, and token budgets
  are bounded at the MCP tool layer.
- Secrets and credentials should never be stored as memory.

## Local Deployment

```mermaid
flowchart LR
    Env[".env"]
    Compose["docker compose"]
    PGData["C:\\ai\\memory-postgres-data"]
    DB["pgvector/pgvector:pg16"]
    Python["Editable Python install"]
    MCP["memory-mcp"]

    Env --> Compose --> DB
    PGData --> DB
    Python --> MCP --> DB
```

The default database binds to `127.0.0.1` and stores PostgreSQL files in a host
directory outside the repository. Keep that directory protected because it can
contain personal, project, and sensitive memory.
