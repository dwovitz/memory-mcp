# Implementation Prompt — P1 Entity Graph MCP Tools

**Model:** Sonnet
**Estimated effort:** 4–8 hrs
**Branch:** `feat/p1-entity-graph`

## Context

`Entity` and `Relationship` tables and repositories already exist on main
(`src/memory_mcp/repositories/entities.py`, `repositories/relationships.py`).
`search_entities` is already an MCP tool (QW4). This track adds four more MCP tools:
`upsert_entity`, `link_entities`, `traverse_entity_graph`, and `get_related_memories`.

## Relevant files

- Modify: `src/memory_mcp/mcp_tools/server.py` — add 4 new tools
- Modify: `src/memory_mcp/retrieval/service.py` — add graph traversal helpers
- Modify: `src/memory_mcp/repositories/entities.py` — add upsert + traversal queries
- Modify: `src/memory_mcp/repositories/relationships.py` — add link + neighbor queries
- Test: `tests/test_entity_graph_tools.py` (new)

## Step 1: Read existing code first

Before writing anything, read:
- `src/memory_mcp/repositories/entities.py` — understand Entity model and existing queries
- `src/memory_mcp/repositories/relationships.py` — understand Relationship model
- `src/memory_mcp/models/schema.py` — Entity and Relationship column definitions
- Top 60 lines of `src/memory_mcp/mcp_tools/server.py` — understand imports and helpers

This is required — the MCP tool signatures must match existing model field names exactly.

## Step 2: Write failing tests

```python
# tests/test_entity_graph_tools.py
import pytest


def test_upsert_entity_creates_new(mcp_client):
    result = mcp_client.call("upsert_entity", {
        "entity_type": "service",
        "name": "UCX.RequestRouting",
        "aliases": ["request-routing"],
        "attributes": {"language": ".NET"},
        "workspace": "ucx-root",
    })
    assert result["status"] in ("created", "updated")
    assert result["entity"]["name"] == "UCX.RequestRouting"


def test_upsert_entity_is_idempotent(mcp_client):
    args = {"entity_type": "service", "name": "MyService", "workspace": "ws"}
    r1 = mcp_client.call("upsert_entity", args)
    r2 = mcp_client.call("upsert_entity", args)
    assert r1["entity"]["id"] == r2["entity"]["id"]


def test_link_entities(mcp_client):
    e1 = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Producer"})
    e2 = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Consumer"})
    result = mcp_client.call("link_entities", {
        "source_id": e1["entity"]["id"],
        "target_id": e2["entity"]["id"],
        "relationship_type": "produces",
        "description": "Producer emits events consumed by Consumer",
    })
    assert result["status"] in ("created", "updated")


def test_traverse_entity_graph(mcp_client):
    root = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Root"})
    child = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Child"})
    mcp_client.call("link_entities", {
        "source_id": root["entity"]["id"],
        "target_id": child["entity"]["id"],
        "relationship_type": "calls",
    })
    result = mcp_client.call("traverse_entity_graph", {
        "start_entity_id": root["entity"]["id"],
        "max_depth": 1,
    })
    assert result["node_count"] >= 2
    names = [n["name"] for n in result["nodes"]]
    assert "Child" in names


def test_get_related_memories(mcp_client):
    entity = mcp_client.call("upsert_entity", {"entity_type": "service", "name": "Svc"})
    result = mcp_client.call("get_related_memories", {
        "entity_id": entity["entity"]["id"],
    })
    assert "memories" in result
```

## Step 3: Run tests to verify they fail

```bash
pytest tests/test_entity_graph_tools.py -v
```

Expected: ImportError or AttributeError — tools do not exist yet.

## Step 4: Add repository methods

In `src/memory_mcp/repositories/entities.py`, add `upsert_entity`:

```python
def upsert_entity(
    self,
    entity_type: str,
    name: str,
    aliases: list[str] | None = None,
    attributes: dict | None = None,
    applies_to: dict | None = None,
) -> tuple[Entity, str]:
    """Return (entity, status) where status is 'created' or 'updated'."""
    existing = (
        self.session.query(Entity)
        .filter(Entity.entity_type == entity_type, Entity.name == name)
        .first()
    )
    if existing:
        if aliases is not None:
            existing.aliases = aliases
        if attributes is not None:
            existing.attributes = attributes
        if applies_to is not None:
            existing.applies_to = applies_to
        return existing, "updated"
    entity = Entity(
        entity_type=entity_type,
        name=name,
        aliases=aliases or [],
        attributes=attributes or {},
        applies_to=applies_to or {},
    )
    self.session.add(entity)
    self.session.flush()
    return entity, "created"
```

In `src/memory_mcp/repositories/relationships.py`, add `link_entities` and `neighbors`:

```python
def link_entities(
    self,
    source_id: str,
    target_id: str,
    relationship_type: str,
    description: str | None = None,
    evidence: str | None = None,
    applies_to: dict | None = None,
) -> tuple[Relationship, str]:
    existing = (
        self.session.query(Relationship)
        .filter(
            Relationship.source_entity_id == source_id,
            Relationship.target_entity_id == target_id,
            Relationship.relationship_type == relationship_type,
        )
        .first()
    )
    if existing:
        existing.description = description
        return existing, "updated"
    rel = Relationship(
        source_entity_id=source_id,
        target_entity_id=target_id,
        relationship_type=relationship_type,
        description=description,
        evidence=evidence,
        applies_to=applies_to or {},
    )
    self.session.add(rel)
    self.session.flush()
    return rel, "created"

def neighbors(
    self,
    entity_id: str,
    relationship_types: tuple[str, ...] | None = None,
    direction: str = "both",
) -> list[Relationship]:
    from sqlalchemy import or_
    q = self.session.query(Relationship)
    if direction == "outbound":
        q = q.filter(Relationship.source_entity_id == entity_id)
    elif direction == "inbound":
        q = q.filter(Relationship.target_entity_id == entity_id)
    else:
        q = q.filter(
            or_(
                Relationship.source_entity_id == entity_id,
                Relationship.target_entity_id == entity_id,
            )
        )
    if relationship_types:
        q = q.filter(Relationship.relationship_type.in_(relationship_types))
    return q.all()
```

## Step 5: Add graph traversal to HybridRetrievalService

In `src/memory_mcp/retrieval/service.py`, add:

```python
def traverse_entity_graph(
    self,
    start_entity_id: str,
    relationship_types: tuple[str, ...] | None = None,
    direction: str = "both",
    max_depth: int = 2,
    include_memories: bool = True,
    limit: int = 20,
) -> dict:
    from memory_mcp.repositories.entities import EntityRepository
    from memory_mcp.repositories.relationships import RelationshipRepository
    from memory_mcp.models.schema import Memory

    entity_repo = EntityRepository(self.session)
    rel_repo = RelationshipRepository(self.session)

    visited_ids: set[str] = set()
    nodes: list[dict] = []
    edges: list[dict] = []
    queue = [(start_entity_id, 0)]

    while queue and len(nodes) < limit:
        eid, depth = queue.pop(0)
        if eid in visited_ids or depth > max_depth:
            continue
        visited_ids.add(eid)
        entity = entity_repo.get_by_id(eid)
        if entity is None:
            continue
        nodes.append({
            "id": str(entity.id),
            "entity_type": entity.entity_type,
            "name": entity.name,
            "aliases": entity.aliases or [],
            "attributes": entity.attributes or {},
        })
        if depth < max_depth:
            rels = rel_repo.neighbors(eid, relationship_types, direction)
            for rel in rels:
                neighbor_id = (
                    str(rel.target_entity_id)
                    if str(rel.source_entity_id) == eid
                    else str(rel.source_entity_id)
                )
                edges.append({
                    "source": str(rel.source_entity_id),
                    "target": str(rel.target_entity_id),
                    "type": rel.relationship_type,
                    "description": rel.description,
                })
                if neighbor_id not in visited_ids:
                    queue.append((neighbor_id, depth + 1))

    memories: list[dict] = []
    if include_memories:
        for node in nodes[:10]:
            ms = self.session.query(Memory).filter(
                Memory.entity_id == node["id"],
                Memory.status == "active",
            ).limit(3).all()
            for m in ms:
                memories.append({"entity_id": node["id"], "memory_id": str(m.id),
                                  "content": m.content})

    return {
        "start_entity_id": start_entity_id,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "memories": memories,
    }
```

Note: check `entity_repo` for a `get_by_id` method — if it doesn't exist, add it:
```python
def get_by_id(self, entity_id: str) -> Entity | None:
    return self.session.query(Entity).filter(Entity.id == entity_id).first()
```

## Step 6: Add MCP tool wrappers in server.py

Add these four tools after `search_entities` and before `run()`. Read the top of server.py first to match existing import and helper patterns exactly.

```python
@mcp.tool()
def upsert_entity(
    entity_type: str,
    name: str,
    aliases: list[str] | None = None,
    attributes: dict[str, Any] | None = None,
    workspace: str | None = None,
    repo: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Create or update a named entity in the knowledge graph."""
    entity_type = _validate_text("entity_type", entity_type, max_chars=100)
    name = _validate_text("name", name, max_chars=500)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    repo = _validate_text("repo", repo, max_chars=200)
    project = _validate_text("project", project, max_chars=200) or repo
    _authorize_tool_call("upsert_entity", AuthAction.WRITE, workspace=workspace, project=project)
    applies_to: dict[str, Any] = {}
    if workspace:
        applies_to["workspace"] = workspace
    if project:
        applies_to["project"] = project
    with session_scope() as session:
        from memory_mcp.repositories.entities import EntityRepository
        repo_obj = EntityRepository(session)
        entity, status = repo_obj.upsert_entity(
            entity_type=entity_type,
            name=name,
            aliases=aliases,
            attributes=attributes,
            applies_to=applies_to or None,
        )
        session.commit()
        return {
            "status": status,
            "entity": {
                "id": str(entity.id),
                "entity_type": entity.entity_type,
                "name": entity.name,
                "aliases": entity.aliases or [],
                "attributes": entity.attributes or {},
                "applies_to": entity.applies_to or {},
            },
        }


@mcp.tool()
def link_entities(
    source_id: str,
    target_id: str,
    relationship_type: str,
    description: str | None = None,
    evidence: str | None = None,
    workspace: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Create or update a directed relationship between two entities."""
    source_id = _validate_text("source_id", source_id, max_chars=100)
    target_id = _validate_text("target_id", target_id, max_chars=100)
    relationship_type = _validate_text("relationship_type", relationship_type, max_chars=100)
    workspace = _validate_text("workspace", workspace, max_chars=200)
    project = _validate_text("project", project, max_chars=200)
    _authorize_tool_call("link_entities", AuthAction.WRITE, workspace=workspace, project=project)
    applies_to: dict[str, Any] = {}
    if workspace:
        applies_to["workspace"] = workspace
    if project:
        applies_to["project"] = project
    with session_scope() as session:
        from memory_mcp.repositories.relationships import RelationshipRepository
        rel_repo = RelationshipRepository(session)
        rel, status = rel_repo.link_entities(
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
            description=description,
            evidence=evidence,
            applies_to=applies_to or None,
        )
        session.commit()
        return {
            "status": status,
            "relationship": {
                "source_id": str(rel.source_entity_id),
                "target_id": str(rel.target_entity_id),
                "type": rel.relationship_type,
                "description": rel.description,
            },
        }


@mcp.tool()
def traverse_entity_graph(
    start_entity_id: str,
    relationship_types: list[str] | None = None,
    direction: str = "both",
    max_depth: int = 2,
    include_memories: bool = True,
    limit: int = 20,
) -> dict[str, Any]:
    """BFS traversal of the entity graph from a starting entity."""
    start_entity_id = _validate_text("start_entity_id", start_entity_id, max_chars=100)
    direction = direction if direction in ("outbound", "inbound", "both") else "both"
    max_depth = _bounded_int("max_depth", max_depth, minimum=1, maximum=4)
    limit = _bounded_int("limit", limit, minimum=1, maximum=100)
    _authorize_tool_call("traverse_entity_graph", AuthAction.READ)
    with session_scope() as session:
        retrieval = HybridRetrievalService(session)
        return retrieval.traverse_entity_graph(
            start_entity_id=start_entity_id,
            relationship_types=_tuple_or_none(relationship_types),
            direction=direction,
            max_depth=max_depth,
            include_memories=include_memories,
            limit=limit,
        )


@mcp.tool()
def get_related_memories(
    entity_id: str,
    relationship_types: list[str] | None = None,
    direction: str = "both",
    limit: int = 20,
) -> dict[str, Any]:
    """Return memories attached to an entity and its direct neighbors."""
    entity_id = _validate_text("entity_id", entity_id, max_chars=100)
    direction = direction if direction in ("outbound", "inbound", "both") else "both"
    limit = _bounded_int("limit", limit, minimum=1, maximum=MAX_SEARCH_LIMIT)
    _authorize_tool_call("get_related_memories", AuthAction.READ)
    with session_scope() as session:
        retrieval = HybridRetrievalService(session)
        result = retrieval.traverse_entity_graph(
            start_entity_id=entity_id,
            relationship_types=_tuple_or_none(relationship_types),
            direction=direction,
            max_depth=1,
            include_memories=True,
            limit=limit,
        )
        return {
            "entity_id": entity_id,
            "memories": result["memories"],
            "neighbor_count": result["node_count"] - 1,
        }
```

## Step 7: Syntax check and tests

```bash
python -c "import ast; ast.parse(open('src/memory_mcp/mcp_tools/server.py').read())"
pytest tests/test_entity_graph_tools.py -v
pytest -v
```

## Step 8: Update docs/ARCHITECTURE.md MCP tool surface table

Add rows:
- `upsert_entity` | Create or update a named entity in the knowledge graph.
- `link_entities` | Create or update a directed relationship between two entities.
- `traverse_entity_graph` | BFS walk from a starting entity, returns nodes, edges, attached memories.
- `get_related_memories` | Return memories attached to an entity and its direct neighbors.

## Merge

```bash
git checkout main
git merge feat/p1-entity-graph --no-ff -m "feat: add P1 entity graph MCP tools (upsert, link, traverse, related)"
git push origin main
```

## Handoff prompt for Track 5

```
Continue memory-mcp roadmap. Track 4 (P1 entity graph tools) is complete and merged to main.
Next: Track 5 — read docs/prompts/impl-p1-code-citations.md and implement it.
Branch off main as feat/p1-code-citations. Use Sonnet.
Check docs/prompts/ROADMAP.md for current status before starting.
Update ROADMAP.md: change Track 4 status from ⬜ to ✅ before starting Track 5.
```
