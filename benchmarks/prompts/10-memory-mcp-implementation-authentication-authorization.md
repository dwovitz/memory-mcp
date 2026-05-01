# Product Security Prompt: Authentication And Authorization Implementation

Run this from:

```text
D:\git\ai\memory-mcp
```

Implement authentication, authorization, and database-backed audit logging for
`memory-mcp`.

Goal:
Add a provider-neutral security boundary so any remote, shared, HTTPS, hosted
gateway, reverse-proxy, SSE, WebSocket, or multi-user deployment rejects
unauthenticated callers before MCP tool dispatch, while preserving explicit
trusted local stdio development without authentication.

Context:

- `memory-mcp` is local-first today and currently exposes a trusted local MCP
  stdio server backed by PostgreSQL.
- Local stdio usage must remain available without authentication for trusted
  local clients.
- Home deployment is expected to use HTTPS.
- Work deployment may use HTTPS, a hosted gateway, or a reverse proxy depending
  on security requirements.
- Remote/shared deployment modes must deny unauthenticated requests by default.
- Authorization must support authenticated users and service accounts.
- Access may optionally require group membership.
- Project access may optionally be restricted by group grants or explicit
  configuration.
- Service accounts use the same grant model as human users, with optional
  groups or grants to narrow access.
- Audit logs should be database-backed.
- Do not store provider tokens, client secrets, API keys, raw identity payloads,
  or sensitive memory content in memory records or audit logs.

Product changes to implement:

1. Add provider-neutral auth domain models.

   Create a small auth module that can be used by remote adapters without
   coupling core retrieval, synthesis, repositories, or memory models to Okta or
   any other identity provider.

   Include:

   - `AuthenticatedPrincipal`
   - principal type: user or service account
   - `issuer`
   - stable `subject`
   - optional `tenant_id`
   - optional `email` or display name
   - groups
   - roles
   - scopes or permissions
   - authentication method
   - assurance level
   - normalized project/workspace/component grants

   Add a compact authorization request/result model that can express:

   - tool name
   - action: read, write, archive, supersede, prune, admin, sensitive read,
     sensitive echo
   - requested tenant/workspace/project/component/scope path
   - requested sensitivity level
   - allow/deny result
   - denial reason suitable for audit logs without leaking sensitive data

2. Add auth configuration.

   Add explicit auth mode configuration with safe defaults:

   - `trusted_local` for current stdio-only local development.
   - `remote` or equivalent for any HTTP/HTTPS/gateway/proxy mode.
   - Remote mode must fail startup unless authentication and authorization
     configuration is complete.
   - No-auth remote mode must not be available by accident.

   Add group/project grant configuration that supports:

   - global access groups
   - mutation-capable groups
   - sensitive-memory groups
   - admin groups
   - project allow lists by group or explicit config
   - service-account grants through the same mechanism

   Keep configuration provider-neutral. Do not hard-code Okta group names into
   core authorization logic.

3. Add central authorization enforcement.

   Add one central authorization layer before memory operations. Every MCP tool
   should map its request to an authorization action before opening or using a
   database session in remote mode.

   Enforce:

   - unauthenticated remote callers are rejected before tool dispatch
   - read tools require read permission
   - `add_memory` requires write permission for the requested scope
   - `archive_memory` requires archive permission for the target memory
   - `supersede_memory` requires supersede/write permission for the target and
     replacement scopes
   - `run_pruning_pass` requires prune/admin permission
   - `include_sensitive=true` requires sensitive read permission
   - sensitive/private write echo through `include_content` or
     `include_evidence` requires sensitive echo permission
   - workspace/project/component/scope-path requests must be allowed by the
     principal's grants
   - tenant-scoped deployments must not allow cross-tenant reads or writes

   Preserve current env-gated mutation and sensitive-tool behavior for trusted
   local stdio mode, but do not rely on those env flags as the only security
   mechanism in remote mode.

4. Add database-backed audit logging.

   Add a migration and model for audit events.

   Audit:

   - authentication success/failure when available at the app boundary
   - authorization allow/deny
   - memory mutations
   - sensitive-memory access attempts
   - admin/pruning operations

   Store:

   - timestamp
   - actor subject
   - actor issuer
   - principal type
   - tenant id when present
   - tool name
   - action
   - requested resource scope
   - decision
   - denial reason or success reason
   - request id/correlation id when present

   Do not store:

   - provider bearer tokens
   - client secrets
   - API keys
   - raw provider claim payloads
   - memory content
   - evidence
   - sensitive/private payloads

5. Add OIDC/OAuth bearer-token integration points.

   Add provider-neutral interfaces for:

   - token validation
   - principal mapping
   - authorization policy evaluation

   Add implementation scaffolding and tests for OIDC/OAuth 2.0 bearer tokens:

   - validate issuer
   - validate audience
   - validate expiry
   - validate signature
   - validate key id against JWKS
   - reject unsupported algorithms
   - reject unsigned tokens

   Okta coverage should map:

   - `sub`
   - `email`
   - `groups`
   - scopes
   - custom claims

   Keep Okta-specific code in an integration module. Do not embed Okta logic in
   retrieval, synthesis, repositories, models, or core MCP tool functions.

6. Add reverse-proxy and hosted-gateway identity support.

   Support trusted proxy identity only when explicitly configured.

   Require:

   - trusted proxy mode is disabled by default
   - identity headers are trusted only from a controlled deployment path
   - docs instruct operators to strip untrusted incoming identity headers at the
     edge before injecting trusted identity
   - prefer mTLS or signed headers between proxy/gateway and application
   - application-side authorization still runs after proxy authentication

7. Add tests.

   Add focused unit and integration-style tests for:

   - local trusted stdio mode still allows current no-auth behavior
   - remote mode rejects missing principal before tool execution
   - authenticated read succeeds inside allowed project/workspace/component
   - authenticated read is denied outside allowed project/workspace/component
   - mutation tools are denied without mutation grant
   - mutation tools succeed with mutation grant and correct scope
   - sensitive reads are denied without sensitive grant
   - sensitive reads succeed with sensitive grant
   - sensitive/private write echo is denied without sensitive echo grant
   - tenant isolation blocks cross-tenant access
   - user and service-account principals use the same grant model
   - optional group grants narrow access correctly
   - authorization denials create database audit events
   - memory mutations create database audit events without memory content
   - invalid OIDC tokens are rejected for wrong issuer, wrong audience, expiry,
     unknown key id, unsupported algorithm, and unsigned token
   - reverse-proxy headers are ignored unless trusted proxy mode is enabled
   - trusted proxy principal mapping still requires authorization

8. Update documentation.

   Update:

   - `README.md`
   - `CLIENT_SETUP_README.md`
   - `SECURITY.md`
   - `docs/ARCHITECTURE.md`
   - `examples/mcp_tools.md` if tool behavior examples need security notes

   Document:

   - trusted local stdio mode
   - remote mode deny-by-default behavior
   - HTTPS home deployment expectations
   - work deployment options: HTTPS, hosted gateway, reverse proxy
   - group-based access
   - optional project restrictions by group or config
   - service-account grants
   - database-backed audit logging
   - Okta setup requirements without storing secrets
   - Microsoft Entra ID, Google Workspace, Auth0, and Keycloak mapping notes
   - reverse-proxy trusted-header requirements

Likely files:

- `src/memory_mcp/config.py`
- `src/memory_mcp/main.py`
- `src/memory_mcp/mcp_tools/server.py`
- `src/memory_mcp/db/connection.py`
- `src/memory_mcp/models/schema.py`
- `src/memory_mcp/models/__init__.py`
- `src/memory_mcp/services/memory_service.py`
- `src/memory_mcp/retrieval/service.py`
- `migrations/versions/*.py`
- `tests/test_mcp_tools.py`
- `tests/test_memory_service.py`
- `tests/test_repositories.py`
- `README.md`
- `CLIENT_SETUP_README.md`
- `SECURITY.md`
- `docs/ARCHITECTURE.md`

Likely new files:

- `src/memory_mcp/auth/__init__.py`
- `src/memory_mcp/auth/models.py`
- `src/memory_mcp/auth/config.py`
- `src/memory_mcp/auth/policy.py`
- `src/memory_mcp/auth/context.py`
- `src/memory_mcp/auth/oidc.py`
- `src/memory_mcp/auth/proxy.py`
- `src/memory_mcp/audit/__init__.py`
- `src/memory_mcp/audit/service.py`
- `src/memory_mcp/repositories/audit.py`
- `tests/test_auth_policy.py`
- `tests/test_auth_oidc.py`
- `tests/test_auth_proxy.py`
- `tests/test_audit_logging.py`

Constraints:

- Do not loosen sensitive/private memory gating.
- Do not remove current local stdio workflow.
- Do not hard-code Okta into core memory, retrieval, synthesis, or repository
  code.
- Do not store secrets, tokens, raw identity payloads, or sensitive memory
  payloads in audit logs.
- Preserve existing MCP tool names unless a migration plan and compatibility
  docs are added.
- Keep the implementation incremental and testable.
- Avoid broad formatting churn.
- Prefer deny-by-default behavior for all remote/shared deployment paths.

Suggested implementation phases:

1. Add auth models, config parsing, and policy tests without changing tool
   behavior.
2. Add audit schema, migration, repository, service, and tests.
3. Add central authorization helpers and wire them into MCP tools while keeping
   trusted local stdio behavior unchanged.
4. Add OIDC token validation and principal mapping tests.
5. Add reverse-proxy principal mapping tests.
6. Add documentation.
7. Run full tests and a local smoke test.

Run tests:

```powershell
pytest tests/test_auth_policy.py tests/test_audit_logging.py tests/test_mcp_tools.py
pytest tests/test_auth_oidc.py tests/test_auth_proxy.py
pytest
```

If Docker is available after the fix, update and smoke-test the local instance:

```powershell
docker compose build memory-mcp
docker compose up -d postgres
alembic upgrade head
docker compose up -d memory-mcp
docker compose ps
```

End by reporting:

```text
AUTH_IMPLEMENTATION_RESULT
changed_files:
auth_modes:
principal_model:
authorization_rules:
audit_logging:
provider_integrations:
reverse_proxy_support:
docs_updated:
tests_run:
docker_smoke_test:
known_limits:
```
