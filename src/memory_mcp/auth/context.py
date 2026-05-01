"""Per-request auth context for hosted adapters."""

from __future__ import annotations

from contextvars import ContextVar
from contextlib import contextmanager
from collections.abc import Iterator

from memory_mcp.auth.models import AuthenticatedPrincipal

_CURRENT_PRINCIPAL: ContextVar[AuthenticatedPrincipal | None] = ContextVar(
    "memory_mcp_current_principal",
    default=None,
)
_CURRENT_REQUEST_ID: ContextVar[str | None] = ContextVar("memory_mcp_current_request_id", default=None)


def get_current_principal() -> AuthenticatedPrincipal | None:
    return _CURRENT_PRINCIPAL.get()


def get_current_request_id() -> str | None:
    return _CURRENT_REQUEST_ID.get()


@contextmanager
def auth_context(
    principal: AuthenticatedPrincipal | None,
    *,
    request_id: str | None = None,
) -> Iterator[None]:
    principal_token = _CURRENT_PRINCIPAL.set(principal)
    request_token = _CURRENT_REQUEST_ID.set(request_id)
    try:
        yield
    finally:
        _CURRENT_PRINCIPAL.reset(principal_token)
        _CURRENT_REQUEST_ID.reset(request_token)
