"""Provider-neutral authorization policy evaluation."""

from __future__ import annotations

from memory_mcp.auth.config import AuthConfig, AuthMode, ProjectGrant
from memory_mcp.auth.models import AuthAction, AuthenticatedPrincipal, AuthorizationRequest, AuthorizationResult


class AuthorizationPolicy:
    """Evaluate MCP authorization requests against provider-neutral grants."""

    def __init__(self, config: AuthConfig) -> None:
        self.config = config

    def evaluate(
        self,
        principal: AuthenticatedPrincipal | None,
        request: AuthorizationRequest,
    ) -> AuthorizationResult:
        if self.config.mode == AuthMode.TRUSTED_LOCAL:
            return AuthorizationResult(True, "trusted_local")
        if principal is None:
            return AuthorizationResult(False, "missing_principal")
        if (
            principal.tenant_id
            and request.resource.tenant_id
            and principal.tenant_id != request.resource.tenant_id
        ):
            return AuthorizationResult(False, "tenant_mismatch")

        if request.action == AuthAction.ADMIN:
            return self._require_group(principal, self.config.policy.admin_groups, "admin_grant_required")
        if request.action == AuthAction.PRUNE:
            return self._require_group(principal, self.config.policy.admin_groups, "admin_grant_required")
        if request.action == AuthAction.SENSITIVE_READ:
            return self._require_group(
                principal,
                self.config.policy.sensitive_memory_groups,
                "sensitive_grant_required",
            )
        if request.action == AuthAction.SENSITIVE_ECHO:
            return self._require_group(
                principal,
                self.config.policy.sensitive_echo_groups,
                "sensitive_echo_grant_required",
            )
        if request.action in {AuthAction.WRITE, AuthAction.ARCHIVE, AuthAction.SUPERSEDE}:
            mutation = self._require_group(
                principal,
                self.config.policy.mutation_groups,
                "mutation_grant_required",
            )
            if not mutation.allowed:
                return mutation

        return self._evaluate_scope(principal, request)

    def _evaluate_scope(
        self,
        principal: AuthenticatedPrincipal,
        request: AuthorizationRequest,
    ) -> AuthorizationResult:
        if self.config.policy.project_grants:
            for grant in self.config.policy.project_grants:
                if self._grant_matches_resource(grant, request) and self._principal_matches_grant(principal, grant):
                    return AuthorizationResult(True, "allowed")
            return AuthorizationResult(False, "scope_not_granted")
        if self.config.policy.global_access_groups:
            return self._require_group(
                principal,
                self.config.policy.global_access_groups,
                "global_access_grant_required",
            )
        return AuthorizationResult(True, "allowed")

    def _require_group(
        self,
        principal: AuthenticatedPrincipal,
        allowed_groups: frozenset[str],
        denial_reason: str,
    ) -> AuthorizationResult:
        if allowed_groups and principal.grant_identifiers().intersection(allowed_groups):
            return AuthorizationResult(True, "allowed")
        return AuthorizationResult(False, denial_reason)

    def _principal_matches_grant(self, principal: AuthenticatedPrincipal, grant: ProjectGrant) -> bool:
        if not grant.groups and not grant.subjects:
            return False
        identifiers = principal.grant_identifiers()
        return bool(identifiers.intersection(grant.groups) or identifiers.intersection(grant.subjects))

    def _grant_matches_resource(self, grant: ProjectGrant, request: AuthorizationRequest) -> bool:
        resource = request.resource
        if grant.workspace and resource.workspace and grant.workspace != resource.workspace:
            return False
        if grant.project and resource.project and grant.project != resource.project:
            return False
        if grant.component and resource.component and grant.component != resource.component:
            return False
        return True
