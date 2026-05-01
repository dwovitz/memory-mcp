"""Database-backed audit logging service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from memory_mcp.auth.models import AuthAction, AuthorizationResult, PrincipalType, ResourceScope
from memory_mcp.repositories.audit import AuditRepository


class AuditService:
    """Application service for security audit events."""

    def __init__(self, session: Session) -> None:
        self.repository = AuditRepository(session)

    def record_authorization(
        self,
        *,
        principal_subject: str | None,
        principal_issuer: str | None,
        principal_type: PrincipalType | None,
        tenant_id: str | None,
        tool_name: str,
        action: AuthAction,
        resource: ResourceScope,
        result: AuthorizationResult,
        request_id: str | None = None,
    ):
        return self.repository.record(
            actor_subject=principal_subject,
            actor_issuer=principal_issuer,
            principal_type=principal_type.value if principal_type else None,
            tenant_id=tenant_id,
            tool_name=tool_name,
            action=action.value,
            resource_scope=resource.to_dict(),
            decision="allow" if result.allowed else "deny",
            reason=result.reason,
            request_id=request_id,
        )
