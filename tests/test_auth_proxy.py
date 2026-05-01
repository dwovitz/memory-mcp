"""Trusted reverse-proxy identity mapping tests."""

from __future__ import annotations

from memory_mcp.auth.config import AuthConfig, AuthMode, TrustedProxyConfig
from memory_mcp.auth.models import AuthAction, AuthorizationRequest, ResourceScope
from memory_mcp.auth.policy import AuthorizationPolicy
from memory_mcp.auth.proxy import principal_from_proxy_headers


def test_proxy_headers_are_ignored_unless_trusted_proxy_is_enabled() -> None:
    principal = principal_from_proxy_headers(
        {
            "x-memory-mcp-subject": "alice",
            "x-memory-mcp-issuer": "proxy",
        },
        TrustedProxyConfig(enabled=False),
    )

    assert principal is None


def test_trusted_proxy_headers_map_principal_and_still_require_authorization() -> None:
    principal = principal_from_proxy_headers(
        {
            "x-memory-mcp-subject": "svc-memory",
            "x-memory-mcp-issuer": "edge-proxy",
            "x-memory-mcp-principal-type": "service_account",
            "x-memory-mcp-groups": "svc-memory",
            "x-memory-mcp-tenant-id": "tenant-a",
        },
        TrustedProxyConfig(enabled=True, allowed_issuer="edge-proxy"),
    )

    assert principal is not None
    assert principal.subject == "svc-memory"
    policy = AuthorizationPolicy(AuthConfig.remote_for_tests())
    result = policy.evaluate(
        principal,
        AuthorizationRequest(
            tool_name="search_memory",
            action=AuthAction.READ,
            resource=ResourceScope(tenant_id="tenant-a", project="memory-mcp"),
        ),
    )

    assert result.allowed is True


def test_trusted_proxy_rejects_unexpected_issuer_header() -> None:
    principal = principal_from_proxy_headers(
        {
            "x-memory-mcp-subject": "alice",
            "x-memory-mcp-issuer": "untrusted",
        },
        TrustedProxyConfig(enabled=True, allowed_issuer="edge-proxy"),
    )

    assert principal is None
