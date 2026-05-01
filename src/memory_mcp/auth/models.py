"""Provider-neutral auth domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PrincipalType(StrEnum):
    """Supported authenticated actor types."""

    USER = "user"
    SERVICE_ACCOUNT = "service_account"


class AuthAction(StrEnum):
    """Authorization actions used by MCP tool dispatch."""

    READ = "read"
    WRITE = "write"
    ARCHIVE = "archive"
    SUPERSEDE = "supersede"
    PRUNE = "prune"
    ADMIN = "admin"
    SENSITIVE_READ = "sensitive_read"
    SENSITIVE_ECHO = "sensitive_echo"


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Normalized authenticated identity independent of any identity provider."""

    principal_type: PrincipalType
    issuer: str
    subject: str
    tenant_id: str | None = None
    email: str | None = None
    display_name: str | None = None
    groups: frozenset[str] = field(default_factory=frozenset)
    roles: frozenset[str] = field(default_factory=frozenset)
    scopes: frozenset[str] = field(default_factory=frozenset)
    auth_method: str = "unknown"
    assurance_level: str | None = None
    grants: frozenset[str] = field(default_factory=frozenset)

    def grant_identifiers(self) -> frozenset[str]:
        """Return all grant identifiers that can match policy grants."""

        return frozenset({self.subject, *self.groups, *self.roles, *self.scopes, *self.grants})


@dataclass(frozen=True)
class ResourceScope:
    """Normalized resource coordinates used in authorization and audit logs."""

    tenant_id: str | None = None
    workspace: str | None = None
    project: str | None = None
    component: str | None = None
    scope_path: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {}
        for key in ("tenant_id", "workspace", "project", "component"):
            value = getattr(self, key)
            if value:
                data[key] = value
        if self.scope_path:
            data["scope_path"] = list(self.scope_path)
        return data


@dataclass(frozen=True)
class AuthorizationRequest:
    """Compact authorization request for one MCP tool operation."""

    tool_name: str
    action: AuthAction
    resource: ResourceScope = field(default_factory=ResourceScope)
    requested_sensitivity: str = "normal"


@dataclass(frozen=True)
class AuthorizationResult:
    """Authorization decision safe to persist in audit logs."""

    allowed: bool
    reason: str
