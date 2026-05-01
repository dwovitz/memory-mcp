"""Repository for security audit events."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from memory_mcp.models import AuditEvent

SENSITIVE_AUDIT_KEYS = {
    "api_key",
    "authorization",
    "client_secret",
    "content",
    "evidence",
    "memory_content",
    "provider_payload",
    "raw_claims",
    "token",
}


class AuditRepository:
    """Persist audit events without sensitive payloads."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        actor_subject: str | None,
        actor_issuer: str | None,
        principal_type: str | None,
        tenant_id: str | None,
        tool_name: str,
        action: str,
        resource_scope: dict[str, Any],
        decision: str,
        reason: str,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_subject=actor_subject,
            actor_issuer=actor_issuer,
            principal_type=principal_type,
            tenant_id=tenant_id,
            tool_name=tool_name,
            action=action,
            resource_scope=resource_scope,
            decision=decision,
            reason=reason,
            request_id=request_id,
            metadata_=_sanitize_metadata(metadata or {}),
        )
        self.session.add(event)
        self.session.flush()
        return event


def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key.lower() not in SENSITIVE_AUDIT_KEYS}
