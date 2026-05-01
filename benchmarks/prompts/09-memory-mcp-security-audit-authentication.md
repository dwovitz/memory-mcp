# Product Security Prompt: Authentication And Authorization Audit

Run this from:

```text
D:\git\ai\memory-mcp
```

Perform a thorough security audit and implementation plan for adding
authentication and authorization to `memory-mcp`.

Goal:
Design the security boundary so a remote or shared deployment cannot access the
MCP server unless the caller is authenticated, while preserving trusted local stdio development without authentication.

Context:

- `memory-mcp` is local-first today.
- Local stdio usage should remain no-auth for trusted local clients.
- Any hosted, remote, HTTP, SSE, WebSocket, reverse-proxy, or multi-user server
  mode must require authentication before MCP tool dispatch.
- The design must be provider-neutral so Okta, Microsoft Entra ID, Google
  Workspace, Auth0, Keycloak, reverse proxies, and service-mesh identity can be
  integrated without rewriting retrieval or memory storage logic.
- Authorization must account for mutation tools, sensitive/private memory
  access, workspace/project/component scopes, tenants, service accounts, audit
  logging, and least privilege.

Audit tasks:

1. Inventory all current server entry points and deployment modes.
2. Identify where MCP requests are accepted and where tool dispatch begins.
3. Identify mutation tools and sensitive/private read paths.
4. Identify where authenticated principal context should be introduced.
5. Identify all places authorization checks must run before memory operations.
6. Identify risks from local no-auth mode, Docker deployments, environment
   variables, logs, errors, and database access.
7. Identify test coverage needed for unauthenticated rejection, authenticated
   success, provider claim mapping, authorization denial, mutation gating,
   sensitive-memory gating, tenant isolation, and local no-auth behavior.
8. Identify documentation updates needed in README, CLIENT_SETUP_README, and
   SECURITY.md.

Design requirements:

- Keep authentication at an adapter or gateway boundary.
- Do not hard-code Okta or any other provider into core retrieval, synthesis,
  repository, or memory model code.
- Introduce a provider-neutral principal and authorization interface.
- Make local stdio no-auth an explicit trusted-local mode, not the production
  default for network serving.
- Support OIDC/OAuth 2.0 bearer-token validation for Okta and common providers.
- Support reverse-proxy identity only when headers are injected by a trusted
  proxy path and untrusted incoming identity headers are stripped.
- Do not store provider tokens, client secrets, API keys, or raw identity
  payloads in memory records.
- Prefer deny-by-default behavior for remote deployments.

Okta-specific coverage:

- Validate issuer, audience, expiry, signature, key id, and algorithm against
  Okta JWKS.
- Map Okta `sub`, `email`, `groups`, scopes, and custom claims into the
  internal principal.
- Use Okta groups or scopes to grant read, mutation, sensitive-memory, and
  admin capabilities.
- Document required Okta application and authorization-server settings without
  storing secrets.

Common-provider coverage:

- Microsoft Entra ID: tenant issuer, app roles, scopes, groups, service
  principals.
- Google Workspace: OIDC issuer, audience, hosted-domain claim, group-derived
  roles.
- Auth0: issuer, audience, roles, permissions, organizations, custom claims.
- Keycloak: realm issuer, client roles, realm roles, groups.
- Reverse proxies and service meshes: trusted identity headers, mTLS, signed
  headers, edge header stripping, and application-side authorization.

Output:

Write a security audit and implementation plan with:

```text
SECURITY_AUDIT_RESULT
current_entry_points:
remote_exposure_risks:
recommended_architecture:
principal_model:
authorization_model:
local_no_auth_mode:
provider_integrations:
okta_plan:
other_provider_plan:
test_plan:
documentation_plan:
implementation_phases:
open_questions:
```

Constraints:

- Do not implement the security code in this audit prompt.
- Do not loosen sensitive/private memory gating.
- Do not store or print secrets.
- Keep local development no-auth behavior explicit and documented.
- Prefer small, testable implementation phases.
