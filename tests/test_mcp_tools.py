"""MCP tool helper tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import memory_mcp.mcp_tools.server as server_module
from memory_mcp.auth.config import AuthConfig
from memory_mcp.mcp_tools.server import (
    ALL_SENSITIVITIES,
    DEFAULT_SENSITIVITIES,
    MUTATION_TOOLS_ENV,
    MAX_SEARCH_LIMIT,
    SENSITIVE_TOOLS_ENV,
    _allowed_sensitivities,
    _bounded_int,
    _context_packet_to_dict,
    _domain_profile_applies_to,
    _memory_to_dict,
    _memory_write_to_dict,
    _preference_memory_types,
    _tags_to_dict,
    _validate_json_payload,
    _validate_memory_scope,
    _validate_scope_path,
    _validate_uuid_list,
)
from memory_mcp.models import Memory
from memory_mcp.services import ContextPacket, RequestClassification

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _test_cache_state() -> dict:
    return {
        "namespace": "memory-data",
        "version": "test-version",
        "source_tables": [
            {
                "table": "memories",
                "count": 1,
                "max_updated_at": "2026-04-26T00:00:00+00:00",
            }
        ],
    }


@pytest.fixture(autouse=True)
def stable_cache_state(monkeypatch) -> None:
    monkeypatch.setattr(server_module, "_cache_state_from_session", lambda session: _test_cache_state())


def test_memory_to_dict_is_json_safe_and_can_include_evidence() -> None:
    memory_id = uuid4()
    entity_id = uuid4()
    memory = Memory(
        id=memory_id,
        entity_id=entity_id,
        memory_type="project_fact",
        summary="Uses PostgreSQL.",
        content="memory-mcp uses PostgreSQL.",
        confidence=Decimal("0.950"),
        sensitivity="normal",
        status="active",
        applies_to={"project": "memory-mcp"},
        metadata_={"seed": True},
        evidence=[{"kind": "explicit", "text": "Project requirement."}],
        created_at=datetime(2026, 4, 23, tzinfo=timezone.utc),
        updated_at=datetime(2026, 4, 23, tzinfo=timezone.utc),
    )

    data = _memory_to_dict(memory, include_evidence=True)

    assert data["id"] == str(memory_id)
    assert data["entity_id"] == str(entity_id)
    assert data["confidence"] == 0.95
    assert data["created_at"] == "2026-04-23T00:00:00+00:00"
    assert data["evidence"] == [{"kind": "explicit", "text": "Project requirement."}]


def test_context_packet_to_dict_includes_rendered_and_token_estimates() -> None:
    packet = ContextPacket(
        request="project context",
        classification=RequestClassification(
            domain="project",
            memory_types=("project_fact",),
            scope="development",
        ),
        facts=["Uses PostgreSQL."],
        before_token_estimate=100,
        after_token_estimate=25,
        diagnostics={
            "context_quality": "strong",
            "warnings": [],
            "fallback_attempts": [],
            "suggested_next_action": "answer_from_packet",
            "source_read_policy": "path_enum_only",
            "source_read_budget_tokens": 0,
            "source_read_limits": {
                "source_read_budget_tokens": 0,
                "max_files_before_edit": 0,
                "max_snippets": 0,
                "max_lines_per_snippet": 0,
                "path_enum_allowed": True,
                "source_content_allowed": False,
                "broad_read_disallowed": True,
            },
            "source_read_contract": {
                "version": "source-read-contract/v1",
                "source_read_policy": "path_enum_only",
                "suggested_next_action": "answer_from_packet",
                "pre_edit_limits": {
                    "max_files": 0,
                    "max_snippets": 0,
                    "max_lines_per_snippet": 0,
                },
                "failure_conditions": [],
            },
        },
    )

    data = _context_packet_to_dict(packet)

    assert data["context_quality"] == "strong"
    assert data["warnings"] == []
    assert data["suggested_next_action"] == "answer_from_packet"
    assert data["source_read_policy"] == "path_enum_only"
    assert data["source_read_budget_tokens"] == 0
    # The slim packet dict (commit 42922e6) intentionally omits source_read_limits,
    # source_read_contract, and the nested diagnostics blob — they were static, never
    # parsed programmatically, and added ~1400-2000 redundant tokens per call. The full
    # contract still lives on packet.diagnostics for callers that need it.
    assert "source_read_limits" not in data
    assert "source_read_contract" not in data
    assert "diagnostics" not in data
    assert data["classification"]["domain"] == "project"
    assert data["classification"]["memory_types"] == ["project_fact"]
    assert data["facts"] == ["Uses PostgreSQL."]
    assert data["token_estimates"]["budget"] is None
    assert data["token_estimates"]["reduction_percent"] == 75.0
    assert "# Context Packet" in data["rendered"]


def test_client_docs_explain_source_read_contract_for_skills_and_hooks() -> None:
    client_setup = (PROJECT_ROOT / "CLIENT_SETUP_README.md").read_text(encoding="utf-8")
    workflow = (PROJECT_ROOT / "docs" / "AGENT_WORKFLOW.md").read_text(encoding="utf-8")

    combined = client_setup + "\n" + workflow
    assert "source_read_contract" in combined
    assert "pre_edit_limits.max_snippets" in combined
    assert "bounded snippets count toward `max_snippets`" in combined
    assert "Hook-friendly contract" in combined
    assert "source_read_budget_obeyed" in combined
    assert "exception must be recorded before exceeding the limit" in combined


def test_client_setup_templates_cover_supported_agent_environments() -> None:
    template_paths = {
        "codex": PROJECT_ROOT / "client-setups" / "codex" / "AGENTS.md",
        "codex_config": PROJECT_ROOT / "client-setups" / "codex" / "config.example.toml",
        "claude": PROJECT_ROOT / "client-setups" / "claude-code" / "CLAUDE.md",
        "claude_hooks": PROJECT_ROOT / "client-setups" / "claude-code" / "settings.example.json",
        "cursor": PROJECT_ROOT / "client-setups" / "cursor" / ".cursor" / "rules" / "memory-mcp.mdc",
        "copilot": PROJECT_ROOT
        / "client-setups"
        / "vscode-copilot"
        / ".github"
        / "copilot-instructions.md",
        "copilot_mcp": PROJECT_ROOT / "client-setups" / "vscode-copilot" / ".vscode" / "mcp.json",
        "common": PROJECT_ROOT / "client-setups" / "common" / "memory-mcp-agent-workflow.md",
    }

    for path in template_paths.values():
        assert path.exists(), f"missing template: {path}"

    instruction_text = "\n".join(
        path.read_text(encoding="utf-8")
        for key, path in template_paths.items()
        if key in {"codex", "claude", "cursor", "copilot", "common"}
    )
    for expected in [
        "get_context_packet",
        "include_global=true",
        "include_sensitive=false",
        "source_read_contract",
        "pre_edit_limits.max_snippets",
        "bounded snippets count toward `max_snippets`",
        "source_read_budget_obeyed",
        "project_memory_refreshed",
    ]:
        assert expected in instruction_text

    for key in {"codex_config", "claude_hooks", "copilot_mcp"}:
        config_text = template_paths[key].read_text(encoding="utf-8")
        assert "memory-mcp" in config_text
        assert "D:\\\\git\\\\ai\\\\memory-mcp" in config_text

    client_setup = (PROJECT_ROOT / "CLIENT_SETUP_README.md").read_text(encoding="utf-8")
    assert "client-setups/codex/AGENTS.md" in client_setup
    assert "client-setups/claude-code/CLAUDE.md" in client_setup
    assert "client-setups/cursor/.cursor/rules/memory-mcp.mdc" in client_setup
    assert "client-setups/vscode-copilot/.github/copilot-instructions.md" in client_setup


def test_preference_domain_mapping() -> None:
    assert _preference_memory_types("coding") == ("coding_preference",)
    assert _preference_memory_types("entertainment") == (
        "entertainment_preference",
        "inferred_preference",
    )
    assert "coding_preference" in _preference_memory_types(None)


def test_domain_profile_applies_to_prefers_person_over_project() -> None:
    assert _domain_profile_applies_to(person_id="person-1", project="memory-mcp") == {
        "person_id": "person-1"
    }
    assert _domain_profile_applies_to(person_id=None, project="memory-mcp") == {
        "project": "memory-mcp"
    }
    assert _domain_profile_applies_to(person_id=None, project=None) is None


def test_sensitive_policy_defaults_to_normal_only(monkeypatch) -> None:
    monkeypatch.delenv(SENSITIVE_TOOLS_ENV, raising=False)

    assert _allowed_sensitivities(False) == DEFAULT_SENSITIVITIES

    with pytest.raises(PermissionError, match="Sensitive MCP access is disabled"):
        _allowed_sensitivities(True)

    monkeypatch.setenv(SENSITIVE_TOOLS_ENV, "true")
    assert _allowed_sensitivities(True) == ALL_SENSITIVITIES


def test_runtime_env_loader_reads_configured_env_file(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MEMORY_MCP_ENABLE_MUTATION_TOOLS=true\n", encoding="utf-8")
    monkeypatch.delenv(MUTATION_TOOLS_ENV, raising=False)
    monkeypatch.setenv("MEMORY_MCP_ENV_FILE", str(env_file))

    server_module._load_runtime_env()

    assert server_module._env_flag(MUTATION_TOOLS_ENV) is True


def test_mcp_bounds_reject_oversized_requests() -> None:
    assert _bounded_int("limit", MAX_SEARCH_LIMIT, minimum=1, maximum=MAX_SEARCH_LIMIT) == MAX_SEARCH_LIMIT

    try:
        _bounded_int("limit", MAX_SEARCH_LIMIT + 1, minimum=1, maximum=MAX_SEARCH_LIMIT)
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("Expected oversized limit to fail")


def test_json_payload_size_is_bounded() -> None:
    try:
        _validate_json_payload("metadata", {"blob": "x" * 20_001}, max_chars=100)
    except ValueError as exc:
        assert "metadata" in str(exc)
    else:
        raise AssertionError("Expected oversized JSON payload to fail")


def test_memory_scope_validator_accepts_known_scopes() -> None:
    assert _validate_memory_scope("component") == "component"
    assert _validate_memory_scope("global") == "global"
    assert _validate_memory_scope("project") == "project"
    assert _validate_memory_scope("workspace") == "workspace"
    assert _validate_memory_scope(None) is None


def test_scope_path_and_override_validators() -> None:
    memory_id = uuid4()

    assert _validate_scope_path(["global", "project:game", "branch:combat"]) == [
        "global",
        "project:game",
        "branch:combat",
    ]
    assert _validate_uuid_list("overrides_memory_ids", [str(memory_id)]) == [str(memory_id)]

    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        _validate_uuid_list("overrides_memory_ids", ["not-a-uuid"])


def test_tags_to_dict_serializes_tag_objects() -> None:
    tag_id = uuid4()
    memory_id = uuid4()
    tags = _tags_to_dict(
        [
            SimpleNamespace(
                id=tag_id,
                memory_id=memory_id,
                tag="project",
                status="active",
            )
        ]
    )

    assert tags == [
        {
            "id": str(tag_id),
            "memory_id": str(memory_id),
            "tag": "project",
            "status": "active",
        }
    ]


def test_memory_write_to_dict_omits_content_and_evidence_by_default() -> None:
    memory = Memory(
        id=uuid4(),
        memory_type="project_fact",
        summary="Short summary.",
        content="Sensitive implementation detail.",
        evidence=[{"kind": "explicit", "text": "Source detail."}],
        sensitivity="normal",
        status="active",
    )

    default_data = _memory_write_to_dict(memory)
    echoed_data = _memory_write_to_dict(memory, include_content=True, include_evidence=True)

    assert "content" not in default_data
    assert "summary" not in default_data
    assert "evidence" not in default_data
    assert echoed_data["content"] == "Sensitive implementation detail."
    assert echoed_data["evidence"] == [{"kind": "explicit", "text": "Source detail."}]


def test_cache_metadata_marks_hits_and_misses() -> None:
    miss = server_module._cache_metadata(_test_cache_state(), hit=False)
    hit = server_module._cached_response(_test_cache_state())

    assert miss["namespace"] == "memory-data"
    assert miss["version"] == "test-version"
    assert miss["hit"] is False
    assert hit == {
        "cached": True,
        "cache": {
            "namespace": "memory-data",
            "version": "test-version",
            "hit": True,
            "source_tables": _test_cache_state()["source_tables"],
        },
    }


def test_search_memory_returns_cached_response_for_matching_cache_version(monkeypatch) -> None:
    class FakeScope:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FailingRetrieval:
        def __init__(self, session) -> None:
            raise AssertionError("retrieval should not run when client cache is fresh")

    monkeypatch.setattr(server_module, "HybridRetrievalService", FailingRetrieval)
    monkeypatch.setattr(server_module, "session_scope", lambda: FakeScope())

    result = server_module.search_memory(if_cache_version="test-version")

    assert result["cached"] is True
    assert result["cache"]["hit"] is True
    assert result["cache"]["version"] == "test-version"


def test_remote_mode_rejects_missing_principal_before_session(monkeypatch) -> None:
    def fail_session_scope():
        raise AssertionError("database session should not open before remote auth")

    monkeypatch.setattr(server_module, "_load_auth_config", AuthConfig.remote_for_tests)
    monkeypatch.setattr(server_module, "session_scope", fail_session_scope)

    with pytest.raises(PermissionError, match="missing_principal"):
        server_module.search_memory(project="memory-mcp")


def test_mutation_tools_require_explicit_capability(monkeypatch) -> None:
    monkeypatch.delenv(MUTATION_TOOLS_ENV, raising=False)

    with pytest.raises(PermissionError, match="Mutation MCP tools are disabled"):
        server_module.add_memory(memory_type="project_fact", content="Blocked")


def test_archive_memory_tool_archives_existing_memory(monkeypatch) -> None:
    monkeypatch.setenv(MUTATION_TOOLS_ENV, "true")
    memory_id = uuid4()
    archived = Memory(
        id=memory_id,
        memory_type="project_fact",
        content="Archived memory.",
        status="archived",
        applies_to={"project": "memory-test"},
    )

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def archive_memory(self, parsed_memory_id):
            assert parsed_memory_id == memory_id
            return archived

    class FakeScope:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(server_module, "MemoryService", FakeService)
    monkeypatch.setattr(server_module, "session_scope", lambda: FakeScope())

    result = server_module.archive_memory(str(memory_id))

    assert result["memory"]["id"] == str(memory_id)
    assert result["memory"]["status"] == "archived"
    assert result["cache"]["version"] == "test-version"


def test_supersede_memory_tool_replaces_memory_and_adds_tags(monkeypatch) -> None:
    monkeypatch.setenv(MUTATION_TOOLS_ENV, "true")
    old_memory_id = uuid4()
    new_memory_id = uuid4()
    replacement = Memory(
        id=new_memory_id,
        memory_type="project_fact",
        content="Current repo is a Flask task tracker.",
        status="active",
        applies_to={"memory_scope": "project", "project": "memory-test"},
        supersedes_memory_id=old_memory_id,
    )

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def supersede_memory(self, parsed_memory_id, **kwargs):
            assert parsed_memory_id == old_memory_id
            assert kwargs["applies_to"] == {
                "scope": "development",
                "memory_scope": "project",
                "workspace": "corp-root",
                "project": "memory-test",
            }
            assert kwargs["sensitivity"] is None
            return replacement

        def tag_memory(self, memory_id, tag):
            return SimpleNamespace(
                id=uuid4(),
                memory_id=memory_id,
                tag=tag,
                status="active",
            )

    class FakeScope:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(server_module, "MemoryService", FakeService)
    monkeypatch.setattr(server_module, "session_scope", lambda: FakeScope())

    result = server_module.supersede_memory(
        str(old_memory_id),
        memory_type="project_fact",
        content="Current repo is a Flask task tracker.",
        applies_to={"scope": "development"},
        workspace="corp-root",
        project="memory-test",
        tags=["project", "flask"],
    )

    assert result["superseded_memory_id"] == str(old_memory_id)
    assert result["memory"]["id"] == str(new_memory_id)
    assert result["memory"]["supersedes_memory_id"] == str(old_memory_id)
    assert "content" not in result["memory"]
    assert "evidence" not in result["memory"]
    assert [tag["tag"] for tag in result["tags"]] == ["project", "flask"]
    assert result["cache"]["hit"] is False


def test_supersede_memory_requires_project_for_project_scope(monkeypatch) -> None:
    monkeypatch.setenv(MUTATION_TOOLS_ENV, "true")
    with pytest.raises(ValueError, match="project is required"):
        server_module.supersede_memory(
            str(uuid4()),
            memory_type="project_fact",
            content="Replacement",
            memory_scope="project",
        )


def test_add_memory_infers_component_scope(monkeypatch) -> None:
    monkeypatch.setenv(MUTATION_TOOLS_ENV, "true")
    created = Memory(
        id=uuid4(),
        memory_type="project_fact",
        content="Auth component uses session cookies.",
        applies_to={
            "memory_scope": "component",
            "workspace": "corp-root",
            "project": "payments-api",
            "component": "auth",
            "topic": "sessions",
        },
    )

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def create_memory(self, **kwargs):
            assert kwargs["applies_to"] == {
                "scope": "development",
                "memory_scope": "component",
                "workspace": "corp-root",
                "project": "payments-api",
                "component": "auth",
                "topic": "sessions",
            }
            return created

        def tag_memory(self, memory_id, tag):
            return SimpleNamespace(
                id=uuid4(),
                memory_id=memory_id,
                tag=tag,
                status="active",
            )

    class FakeScope:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(server_module, "MemoryService", FakeService)
    monkeypatch.setattr(server_module, "session_scope", lambda: FakeScope())

    result = server_module.add_memory(
        memory_type="project_fact",
        content="Auth component uses session cookies.",
        applies_to={"scope": "development"},
        workspace="corp-root",
        project="payments-api",
        component="auth",
        topic="sessions",
        tags=["auth"],
    )

    assert result["memory"]["id"] == str(created.id)
    assert "content" not in result["memory"]
    assert result["cache"]["version"] == "test-version"


def test_add_memory_accepts_scope_path_validity_and_branch_override(monkeypatch) -> None:
    monkeypatch.setenv(MUTATION_TOOLS_ENV, "true")
    parent_memory_id = uuid4()
    created = Memory(
        id=uuid4(),
        memory_type="architecture_decision",
        content="Branch uses event-driven input.",
        applies_to={
            "scope_path": [
                "global",
                "project:Metroidvania",
                "module:combat",
                "branch:combat-refactor",
            ],
            "scope_type": "branch",
            "valid_from": "2026-04-24T00:00:00+00:00",
        },
        metadata_={"overrides_memory_ids": [str(parent_memory_id)]},
    )

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def create_memory(self, **kwargs):
            assert kwargs["applies_to"] == created.applies_to
            assert kwargs["metadata"] == {"overrides_memory_ids": [str(parent_memory_id)]}
            return created

    class FakeScope:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(server_module, "MemoryService", FakeService)
    monkeypatch.setattr(server_module, "session_scope", lambda: FakeScope())

    result = server_module.add_memory(
        memory_type="architecture_decision",
        content="Branch uses event-driven input.",
        scope_path=[
            "global",
            "project:Metroidvania",
            "module:combat",
            "branch:combat-refactor",
        ],
        scope_type="branch",
        valid_from="2026-04-24T00:00:00+00:00",
        overrides_memory_ids=[str(parent_memory_id)],
    )

    assert result["memory"]["id"] == str(created.id)


def test_add_memory_preserves_custom_scope_for_scoped_write(monkeypatch) -> None:
    monkeypatch.setenv(MUTATION_TOOLS_ENV, "true")
    created = Memory(
        id=uuid4(),
        memory_type="project_fact",
        content="Release process is documented.",
        applies_to={
            "scope": "release",
            "memory_scope": "project",
            "project": "memory-mcp",
        },
    )

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def create_memory(self, **kwargs):
            assert kwargs["applies_to"] == created.applies_to
            return created

    class FakeScope:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(server_module, "MemoryService", FakeService)
    monkeypatch.setattr(server_module, "session_scope", lambda: FakeScope())

    result = server_module.add_memory(
        memory_type="project_fact",
        content="Release process is documented.",
        applies_to={"scope": "release"},
        project="memory-mcp",
    )

    assert result["memory"]["id"] == str(created.id)


def test_sensitive_write_echo_requires_sensitive_capability(monkeypatch) -> None:
    monkeypatch.setenv(MUTATION_TOOLS_ENV, "true")
    monkeypatch.delenv(SENSITIVE_TOOLS_ENV, raising=False)
    created = Memory(
        id=uuid4(),
        memory_type="personal_fact",
        content="Private detail.",
        evidence=[{"kind": "explicit", "text": "Private evidence."}],
        sensitivity="sensitive",
    )

    class FakeService:
        def __init__(self, session) -> None:
            self.session = session

        def create_memory(self, **kwargs):
            return created

    class FakeScope:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(server_module, "MemoryService", FakeService)
    monkeypatch.setattr(server_module, "session_scope", lambda: FakeScope())

    with pytest.raises(PermissionError, match="Sensitive MCP access is disabled"):
        server_module.add_memory(
            memory_type="personal_fact",
            content="Private detail.",
            sensitivity="sensitive",
            include_content=True,
        )

    result = server_module.add_memory(
        memory_type="personal_fact",
        content="Private detail.",
        sensitivity="sensitive",
    )
    assert "content" not in result["memory"]

    monkeypatch.setenv(SENSITIVE_TOOLS_ENV, "true")
    echoed = server_module.add_memory(
        memory_type="personal_fact",
        content="Private detail.",
        sensitivity="sensitive",
        include_content=True,
        include_evidence=True,
    )
    assert echoed["memory"]["content"] == "Private detail."
    assert echoed["memory"]["evidence"] == [{"kind": "explicit", "text": "Private evidence."}]


def test_component_scope_requires_project_and_component(monkeypatch) -> None:
    monkeypatch.setenv(MUTATION_TOOLS_ENV, "true")
    with pytest.raises(ValueError, match="project is required"):
        server_module.add_memory(
            memory_type="project_fact",
            content="Replacement",
            memory_scope="component",
            component="auth",
        )
    with pytest.raises(ValueError, match="component is required"):
        server_module.add_memory(
            memory_type="project_fact",
            content="Replacement",
            memory_scope="component",
            project="payments-api",
        )
