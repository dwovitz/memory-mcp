"""Database-backed audit logging tests."""

from __future__ import annotations

from memory_mcp.audit.service import AuditService
from memory_mcp.auth.models import AuthAction, AuthorizationResult, PrincipalType, ResourceScope
from memory_mcp.models import AuditEvent
from memory_mcp.repositories.audit import AuditRepository


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.flush_count = 0

    def add(self, value):
        self.added.append(value)

    def flush(self) -> None:
        self.flush_count += 1


def test_audit_repository_records_event_without_sensitive_payloads() -> None:
    session = FakeSession()
    repository = AuditRepository(session)

    event = repository.record(
        actor_subject="alice",
        actor_issuer="https://idp.example.test",
        principal_type=PrincipalType.USER.value,
        tenant_id="tenant-a",
        tool_name="add_memory",
        action=AuthAction.WRITE.value,
        resource_scope={"project": "memory-mcp"},
        decision="allow",
        reason="allowed",
        request_id="req-1",
        metadata={
            "content": "must not be stored",
            "evidence": [{"text": "must not be stored"}],
            "safe": "kept",
        },
    )

    assert isinstance(event, AuditEvent)
    assert session.added == [event]
    assert session.flush_count == 1
    assert event.metadata_ == {"safe": "kept"}
    assert event.resource_scope == {"project": "memory-mcp"}


def test_audit_service_records_authorization_decision() -> None:
    session = FakeSession()
    service = AuditService(session)

    event = service.record_authorization(
        principal_subject="alice",
        principal_issuer="https://idp.example.test",
        principal_type=PrincipalType.USER,
        tenant_id="tenant-a",
        tool_name="search_memory",
        action=AuthAction.SENSITIVE_READ,
        resource=ResourceScope(project="memory-mcp"),
        result=AuthorizationResult(allowed=False, reason="sensitive_grant_required"),
        request_id="req-1",
    )

    assert event.decision == "deny"
    assert event.reason == "sensitive_grant_required"
    assert event.resource_scope == {"project": "memory-mcp"}
