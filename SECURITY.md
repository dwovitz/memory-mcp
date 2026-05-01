# Security

`memory-mcp` is local-first by default. The default supported local deployment
is a stdio MCP server started by a trusted local client, with no network listener
and no end-user authentication layer.

Do not expose a local stdio deployment directly to untrusted users or remote
networks. If `memory-mcp` is placed behind an HTTP, WebSocket, SSE, reverse
proxy, hosted MCP gateway, or multi-user server boundary, that boundary must
require authentication before any MCP request can reach the server.

## Local Development

Local development intentionally does not require authentication:

- Run the server only on a trusted workstation or trusted developer container.
- Keep `.env` local and out of Git.
- Keep Postgres bound to `127.0.0.1` unless a trusted network deployment is
  explicitly designed.
- Enable mutation and sensitive-memory tools only for trusted local clients.
- Do not treat local no-auth mode as acceptable for shared or hosted service
  deployments.

## Production Authentication Requirements

Any production or shared deployment must provide these controls before requests
reach `memory-mcp`:

- Authenticate every user or service account.
- Reject unauthenticated requests before MCP tool dispatch.
- Map the authenticated principal into an internal identity.
- Authorize tool access by principal, tenant, workspace, project, component, and
  sensitivity level.
- Keep mutation tools and sensitive-memory access disabled unless explicitly
  granted.
- Log authentication decisions, authorization denials, and memory mutations
  without logging secrets, tokens, or sensitive memory content.
- Use TLS for all network hops that carry credentials or MCP traffic.
- Prefer short-lived credentials and server-side token validation.

## Integration Model

Authentication should be added through a small provider-neutral boundary rather
than hard-coding one identity system into memory storage, retrieval, or MCP tool
logic.

Recommended architecture:

1. Add an authentication layer at the network/server adapter boundary.
2. Verify credentials and build an `AuthenticatedPrincipal`.
3. Pass principal claims into authorization checks before tool execution.
4. Keep local stdio mode on a no-auth trusted-local adapter.
5. Keep provider-specific code in separate integration modules.

The principal should capture at least:

- `subject`: stable user or service-account id.
- `issuer`: identity provider or trust domain.
- `email` or display name when available.
- `groups` or roles.
- `tenant` or organization id when applicable.
- `scopes` or permissions.
- authentication method and assurance level if available.

Authorization should not depend on raw provider tokens after validation. Convert
provider claims into internal permissions, then enforce those permissions in one
place before calling memory operations.

## Common Providers

### Okta

Okta is usually integrated through OpenID Connect:

- Create an Okta OIDC application for the deployed gateway or server.
- Validate access tokens or ID tokens against Okta's issuer, audience, expiry,
  signature, and key id using Okta JWKS.
- Map Okta `sub`, `email`, `groups`, and custom claims into the internal
  principal.
- Use Okta groups or authorization server scopes to grant read, mutation, and
  sensitive-memory permissions.
- Never store Okta client secrets or tokens in memory records.

### Microsoft Entra ID

For Microsoft Entra ID, use OIDC or OAuth 2.0 bearer tokens:

- Validate issuer, tenant, audience, expiry, signature, and JWKS key id.
- Map `oid`, `tid`, `preferred_username`, groups, app roles, or scopes into the
  internal principal.
- Treat app-only service principals separately from human users.

### Google Workspace

For Google Workspace, use Google OIDC:

- Validate issuer, audience, expiry, signature, and hosted-domain claims where
  appropriate.
- Map `sub`, `email`, `hd`, and groups or directory-derived roles into the
  internal principal.

### Auth0

For Auth0, use OIDC/OAuth 2.0:

- Validate issuer, audience, expiry, signature, and JWKS key id.
- Map Auth0 roles, permissions, organization ids, and custom claims into the
  internal principal.

### Keycloak

For Keycloak, use OIDC:

- Validate realm issuer, audience, expiry, signature, and JWKS key id.
- Map realm roles, client roles, groups, and tenant claims into the internal
  principal.

### Reverse Proxy Or Service Mesh

If authentication is delegated to a proxy, gateway, or service mesh:

- Only trust identity headers from a network path that the application controls.
- Strip incoming identity headers at the edge before injecting trusted ones.
- Prefer signed headers or mTLS between the proxy and application.
- Keep authorization in the application, even when authentication is delegated.

## Security Audit Checklist

Before enabling a remote or shared deployment:

- Confirm there is no unauthenticated network path to MCP tools.
- Confirm local no-auth mode is only reachable by trusted local users.
- Confirm mutation and sensitive tools require explicit authorization.
- Confirm memory queries are scoped by principal and tenant where applicable.
- Confirm errors do not leak tokens, connection strings, private memory content,
  or provider secrets.
- Confirm audit logs identify the actor and action without storing sensitive
  payloads.
- Confirm token validation rejects wrong issuer, wrong audience, expired tokens,
  unsigned tokens, and unsupported algorithms.
- Confirm provider secrets are loaded from secret management, not committed
  files.

## Implemented Security Boundary

The codebase now has provider-neutral auth primitives under `src/memory_mcp/auth`.
`AuthenticatedPrincipal` represents human users and service accounts without
coupling core memory code to Okta, Entra ID, Google Workspace, Auth0, Keycloak,
or another provider. `AuthorizationPolicy` maps each MCP tool request to a
read, write, archive, supersede, prune/admin, sensitive-read, or sensitive-echo
action before tool work runs.

`MEMORY_MCP_AUTH_MODE=trusted_local` is the default for local stdio. Remote mode
requires OIDC issuer/audience configuration or explicit trusted-proxy
configuration and denies missing principals. The legacy mutation and sensitive
environment gates remain in place as compatibility controls; remote deployments
must also configure authorization grants.

Audit events are stored in `audit_events` with actor, issuer, principal type,
tenant, tool, action, resource scope, decision, reason, and request id. Audit
metadata is sanitized so memory content, evidence, tokens, secrets, raw claims,
and provider payloads are not persisted.
