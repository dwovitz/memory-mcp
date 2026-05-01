"""Trusted reverse-proxy identity mapping."""

from __future__ import annotations

from collections.abc import Mapping

from memory_mcp.auth.config import TrustedProxyConfig
from memory_mcp.auth.models import AuthenticatedPrincipal, PrincipalType


def principal_from_proxy_headers(
    headers: Mapping[str, str],
    config: TrustedProxyConfig,
) -> AuthenticatedPrincipal | None:
    """Map configured trusted identity headers into a principal."""

    if not config.enabled:
        return None
    normalized = {key.lower(): value for key, value in headers.items()}
    issuer = normalized.get("x-memory-mcp-issuer")
    subject = normalized.get("x-memory-mcp-subject")
    if not issuer or not subject:
        return None
    if config.allowed_issuer and issuer != config.allowed_issuer:
        return None
    principal_type = PrincipalType(normalized.get("x-memory-mcp-principal-type", PrincipalType.USER.value))
    return AuthenticatedPrincipal(
        principal_type=principal_type,
        issuer=issuer,
        subject=subject,
        tenant_id=normalized.get("x-memory-mcp-tenant-id"),
        email=normalized.get("x-memory-mcp-email"),
        display_name=normalized.get("x-memory-mcp-display-name"),
        groups=_csv_header(normalized.get("x-memory-mcp-groups")),
        roles=_csv_header(normalized.get("x-memory-mcp-roles")),
        scopes=_csv_header(normalized.get("x-memory-mcp-scopes")),
        auth_method="trusted_proxy",
        assurance_level=normalized.get("x-memory-mcp-assurance-level"),
    )


def _csv_header(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    return frozenset(part.strip() for part in value.split(",") if part.strip())
