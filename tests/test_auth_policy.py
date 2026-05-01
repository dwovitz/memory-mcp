"""Provider-neutral authorization policy tests."""

from __future__ import annotations

from memory_mcp.auth.config import AuthConfig, AuthMode, AuthPolicyConfig, ProjectGrant
from memory_mcp.auth.models import (
    AuthAction,
    AuthenticatedPrincipal,
    AuthorizationRequest,
    PrincipalType,
    ResourceScope,
)
from memory_mcp.auth.policy import AuthorizationPolicy


def _principal(
    *,
    groups: list[str] | None = None,
    principal_type: PrincipalType = PrincipalType.USER,
    tenant_id: str | None = "tenant-a",
) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        principal_type=principal_type,
        issuer="https://idp.example.test",
        subject="alice",
        tenant_id=tenant_id,
        email="alice@example.test",
        groups=frozenset(groups or []),
        roles=frozenset(),
        scopes=frozenset(),
        auth_method="oidc_bearer",
        assurance_level="aal2",
    )


def _request(
    action: AuthAction,
    *,
    project: str | None = "memory-mcp",
    include_sensitive: bool = False,
    tenant_id: str | None = "tenant-a",
) -> AuthorizationRequest:
    return AuthorizationRequest(
        tool_name="search_memory",
        action=action,
        resource=ResourceScope(
            tenant_id=tenant_id,
            workspace="ai",
            project=project,
            component="auth",
        ),
        requested_sensitivity="sensitive" if include_sensitive else "normal",
    )


def test_trusted_local_mode_allows_without_principal() -> None:
    policy = AuthorizationPolicy(AuthConfig(mode=AuthMode.TRUSTED_LOCAL))

    result = policy.evaluate(None, _request(AuthAction.READ))

    assert result.allowed is True
    assert result.reason == "trusted_local"


def test_remote_mode_denies_missing_principal() -> None:
    policy = AuthorizationPolicy(AuthConfig.remote_for_tests())

    result = policy.evaluate(None, _request(AuthAction.READ))

    assert result.allowed is False
    assert result.reason == "missing_principal"


def test_authenticated_read_succeeds_inside_allowed_project() -> None:
    policy = AuthorizationPolicy(
        AuthConfig(
            mode=AuthMode.REMOTE,
            policy=AuthPolicyConfig(
                global_access_groups=frozenset({"readers"}),
                project_grants=(
                    ProjectGrant(project="memory-mcp", groups=frozenset({"readers"})),
                ),
            ),
            oidc_issuer="https://idp.example.test",
            oidc_audience="memory-mcp",
        )
    )

    result = policy.evaluate(_principal(groups=["readers"]), _request(AuthAction.READ))

    assert result.allowed is True
    assert result.reason == "allowed"


def test_authenticated_read_is_denied_outside_allowed_project() -> None:
    policy = AuthorizationPolicy(
        AuthConfig(
            mode=AuthMode.REMOTE,
            policy=AuthPolicyConfig(
                project_grants=(
                    ProjectGrant(project="memory-mcp", groups=frozenset({"readers"})),
                ),
            ),
            oidc_issuer="https://idp.example.test",
            oidc_audience="memory-mcp",
        )
    )

    result = policy.evaluate(_principal(groups=["readers"]), _request(AuthAction.READ, project="other"))

    assert result.allowed is False
    assert result.reason == "scope_not_granted"


def test_mutations_require_mutation_group() -> None:
    config = AuthConfig(
        mode=AuthMode.REMOTE,
        policy=AuthPolicyConfig(
            global_access_groups=frozenset({"readers"}),
            mutation_groups=frozenset({"writers"}),
            project_grants=(
                ProjectGrant(project="memory-mcp", groups=frozenset({"readers", "writers"})),
            ),
        ),
        oidc_issuer="https://idp.example.test",
        oidc_audience="memory-mcp",
    )
    policy = AuthorizationPolicy(config)

    denied = policy.evaluate(_principal(groups=["readers"]), _request(AuthAction.WRITE))
    allowed = policy.evaluate(_principal(groups=["writers"]), _request(AuthAction.WRITE))

    assert denied.allowed is False
    assert denied.reason == "mutation_grant_required"
    assert allowed.allowed is True


def test_sensitive_reads_and_echo_require_separate_grants() -> None:
    config = AuthConfig(
        mode=AuthMode.REMOTE,
        policy=AuthPolicyConfig(
            sensitive_memory_groups=frozenset({"sensitive-readers"}),
            sensitive_echo_groups=frozenset({"sensitive-echo"}),
        ),
        oidc_issuer="https://idp.example.test",
        oidc_audience="memory-mcp",
    )
    policy = AuthorizationPolicy(config)

    denied_read = policy.evaluate(_principal(groups=[]), _request(AuthAction.SENSITIVE_READ, include_sensitive=True))
    allowed_read = policy.evaluate(
        _principal(groups=["sensitive-readers"]),
        _request(AuthAction.SENSITIVE_READ, include_sensitive=True),
    )
    denied_echo = policy.evaluate(
        _principal(groups=["sensitive-readers"]),
        _request(AuthAction.SENSITIVE_ECHO, include_sensitive=True),
    )
    allowed_echo = policy.evaluate(
        _principal(groups=["sensitive-echo"]),
        _request(AuthAction.SENSITIVE_ECHO, include_sensitive=True),
    )

    assert denied_read.reason == "sensitive_grant_required"
    assert allowed_read.allowed is True
    assert denied_echo.reason == "sensitive_echo_grant_required"
    assert allowed_echo.allowed is True


def test_tenant_isolation_blocks_cross_tenant_access() -> None:
    policy = AuthorizationPolicy(AuthConfig.remote_for_tests())

    result = policy.evaluate(
        _principal(groups=["readers"], tenant_id="tenant-a"),
        _request(AuthAction.READ, tenant_id="tenant-b"),
    )

    assert result.allowed is False
    assert result.reason == "tenant_mismatch"


def test_service_accounts_use_same_grant_model() -> None:
    policy = AuthorizationPolicy(
        AuthConfig(
            mode=AuthMode.REMOTE,
            policy=AuthPolicyConfig(
                mutation_groups=frozenset({"writers"}),
                project_grants=(
                    ProjectGrant(project="memory-mcp", groups=frozenset({"svc-memory"})),
                ),
            ),
            oidc_issuer="https://idp.example.test",
            oidc_audience="memory-mcp",
        )
    )

    result = policy.evaluate(
        _principal(groups=["svc-memory", "writers"], principal_type=PrincipalType.SERVICE_ACCOUNT),
        _request(AuthAction.WRITE),
    )

    assert result.allowed is True
