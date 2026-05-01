"""OIDC/OAuth bearer token validation scaffolding."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from memory_mcp.auth.models import AuthenticatedPrincipal, PrincipalType


class TokenValidationError(ValueError):
    """Raised when a bearer token cannot be trusted."""


class OidcTokenValidator:
    """Validate compact JWT bearer tokens against configured issuer, audience, and JWKS."""

    def __init__(self, *, issuer: str, audience: str, jwks: dict[str, Any]) -> None:
        self.issuer = issuer
        self.audience = audience
        self.keys = {key.get("kid"): key for key in jwks.get("keys", []) if key.get("kid")}

    def validate(self, token: str) -> AuthenticatedPrincipal:
        header, payload, signature, signing_input = self._decode_parts(token)
        alg = header.get("alg")
        if alg == "none":
            raise TokenValidationError("unsigned tokens are not accepted")
        if alg != "HS256":
            raise TokenValidationError(f"unsupported token algorithm: {alg}")
        key = self.keys.get(header.get("kid"))
        if key is None:
            raise TokenValidationError("unknown token kid")
        self._verify_hs256(key, signing_input, signature)
        self._validate_claims(payload)
        return self._principal_from_claims(payload)

    def _decode_parts(self, token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
        parts = token.split(".")
        if len(parts) != 3:
            raise TokenValidationError("token must have three JWT parts")
        header = json.loads(_b64decode(parts[0]))
        payload = json.loads(_b64decode(parts[1]))
        signature = _b64decode(parts[2]) if parts[2] else b""
        return header, payload, signature, f"{parts[0]}.{parts[1]}".encode("ascii")

    def _verify_hs256(self, key: dict[str, Any], signing_input: bytes, signature: bytes) -> None:
        if key.get("kty") != "oct":
            raise TokenValidationError("HS256 validation requires an oct JWKS key")
        secret = _b64decode(key["k"])
        expected = hmac.new(secret, signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise TokenValidationError("token signature verification failed")

    def _validate_claims(self, payload: dict[str, Any]) -> None:
        if payload.get("iss") != self.issuer:
            raise TokenValidationError("token issuer is not trusted")
        audience = payload.get("aud")
        if isinstance(audience, list):
            audience_valid = self.audience in audience
        else:
            audience_valid = audience == self.audience
        if not audience_valid:
            raise TokenValidationError("token audience is not accepted")
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise TokenValidationError("token is expired")
        if not payload.get("sub"):
            raise TokenValidationError("token subject is required")

    def _principal_from_claims(self, payload: dict[str, Any]) -> AuthenticatedPrincipal:
        scopes = payload.get("scope", "")
        scope_values = scopes.split() if isinstance(scopes, str) else scopes or []
        groups = payload.get("groups", [])
        principal_type = PrincipalType(payload.get("principal_type", PrincipalType.USER.value))
        return AuthenticatedPrincipal(
            principal_type=principal_type,
            issuer=payload["iss"],
            subject=payload["sub"],
            tenant_id=payload.get("tenant_id") or payload.get("tid"),
            email=payload.get("email"),
            display_name=payload.get("name"),
            groups=frozenset(groups),
            roles=frozenset(payload.get("roles", [])),
            scopes=frozenset(scope_values),
            auth_method="oidc_bearer",
            assurance_level=payload.get("acr") or payload.get("amr"),
            grants=frozenset(payload.get("grants", [])),
        )


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
