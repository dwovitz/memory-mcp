"""Provider-neutral authentication and authorization primitives."""

from memory_mcp.auth.config import AuthConfig, AuthMode, AuthPolicyConfig, ProjectGrant, TrustedProxyConfig
from memory_mcp.auth.models import (
    AuthAction,
    AuthenticatedPrincipal,
    AuthorizationRequest,
    AuthorizationResult,
    PrincipalType,
    ResourceScope,
)
from memory_mcp.auth.policy import AuthorizationPolicy

__all__ = [
    "AuthAction",
    "AuthConfig",
    "AuthMode",
    "AuthPolicyConfig",
    "AuthenticatedPrincipal",
    "AuthorizationPolicy",
    "AuthorizationRequest",
    "AuthorizationResult",
    "PrincipalType",
    "ProjectGrant",
    "ResourceScope",
    "TrustedProxyConfig",
]
