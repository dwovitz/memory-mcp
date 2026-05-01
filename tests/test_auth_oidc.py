"""OIDC/OAuth bearer token integration tests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest

from memory_mcp.auth.oidc import OidcTokenValidator, TokenValidationError


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _token(payload: dict, *, kid: str = "kid-1", alg: str = "HS256", secret: bytes = b"secret") -> str:
    header = {"typ": "JWT", "alg": alg, "kid": kid}
    signing_input = f"{_b64url(json.dumps(header).encode())}.{_b64url(json.dumps(payload).encode())}"
    signature = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def _validator() -> OidcTokenValidator:
    return OidcTokenValidator(
        issuer="https://idp.example.test",
        audience="memory-mcp",
        jwks={
            "keys": [
                {
                    "kty": "oct",
                    "kid": "kid-1",
                    "alg": "HS256",
                    "k": _b64url(b"secret"),
                }
            ]
        },
    )


def _payload(**overrides) -> dict:
    payload = {
        "iss": "https://idp.example.test",
        "aud": "memory-mcp",
        "sub": "alice",
        "email": "alice@example.test",
        "groups": ["readers"],
        "scope": "read write",
        "exp": int(time.time()) + 300,
    }
    payload.update(overrides)
    return payload


def test_valid_bearer_token_maps_principal_claims() -> None:
    principal = _validator().validate(_token(_payload()))

    assert principal.subject == "alice"
    assert principal.email == "alice@example.test"
    assert "readers" in principal.groups
    assert "write" in principal.scopes
    assert principal.auth_method == "oidc_bearer"


@pytest.mark.parametrize(
    ("payload_overrides", "message"),
    [
        ({"iss": "https://wrong.example.test"}, "issuer"),
        ({"aud": "other-service"}, "audience"),
        ({"exp": int(time.time()) - 10}, "expired"),
    ],
)
def test_invalid_claims_are_rejected(payload_overrides: dict, message: str) -> None:
    with pytest.raises(TokenValidationError, match=message):
        _validator().validate(_token(_payload(**payload_overrides)))


def test_unknown_key_id_is_rejected() -> None:
    with pytest.raises(TokenValidationError, match="kid"):
        _validator().validate(_token(_payload(), kid="missing"))


def test_unsupported_and_unsigned_algorithms_are_rejected() -> None:
    with pytest.raises(TokenValidationError, match="unsupported"):
        _validator().validate(_token(_payload(), alg="HS384"))

    unsigned = f"{_b64url(json.dumps({'alg': 'none', 'kid': 'kid-1'}).encode())}.{_b64url(json.dumps(_payload()).encode())}."
    with pytest.raises(TokenValidationError, match="unsigned"):
        _validator().validate(unsigned)
