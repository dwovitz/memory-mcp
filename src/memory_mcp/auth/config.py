"""Authentication and authorization configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import json
import os
from pathlib import Path
from typing import Self

from dotenv import load_dotenv


class AuthMode(StrEnum):
    """Supported auth deployment modes."""

    TRUSTED_LOCAL = "trusted_local"
    REMOTE = "remote"


@dataclass(frozen=True)
class ProjectGrant:
    """Grant access to a project/workspace/component by group or subject."""

    project: str | None = None
    workspace: str | None = None
    component: str | None = None
    groups: frozenset[str] = field(default_factory=frozenset)
    subjects: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class AuthPolicyConfig:
    """Provider-neutral authorization policy configuration."""

    global_access_groups: frozenset[str] = field(default_factory=frozenset)
    mutation_groups: frozenset[str] = field(default_factory=frozenset)
    sensitive_memory_groups: frozenset[str] = field(default_factory=frozenset)
    sensitive_echo_groups: frozenset[str] = field(default_factory=frozenset)
    admin_groups: frozenset[str] = field(default_factory=frozenset)
    project_grants: tuple[ProjectGrant, ...] = ()


@dataclass(frozen=True)
class TrustedProxyConfig:
    """Trusted reverse-proxy identity header configuration."""

    enabled: bool = False
    allowed_issuer: str | None = None


@dataclass(frozen=True)
class AuthConfig:
    """Process auth configuration."""

    mode: AuthMode = AuthMode.TRUSTED_LOCAL
    policy: AuthPolicyConfig = field(default_factory=AuthPolicyConfig)
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    trusted_proxy: TrustedProxyConfig = field(default_factory=TrustedProxyConfig)

    @classmethod
    def from_env(
        cls,
        env_file: str | Path | None = ".env",
        *,
        require_env_file: bool = False,
    ) -> Self:
        if env_file is not None:
            env_path = Path(env_file)
            if require_env_file and not env_path.is_file():
                raise FileNotFoundError(f"Required environment file not found: {env_path}")
            load_dotenv(dotenv_path=env_path, override=False)

        mode = AuthMode(os.getenv("MEMORY_MCP_AUTH_MODE", AuthMode.TRUSTED_LOCAL.value))
        config = cls(
            mode=mode,
            oidc_issuer=_empty_to_none(os.getenv("MEMORY_MCP_OIDC_ISSUER")),
            oidc_audience=_empty_to_none(os.getenv("MEMORY_MCP_OIDC_AUDIENCE")),
            trusted_proxy=TrustedProxyConfig(
                enabled=_flag("MEMORY_MCP_TRUSTED_PROXY_ENABLED"),
                allowed_issuer=_empty_to_none(os.getenv("MEMORY_MCP_TRUSTED_PROXY_ISSUER")),
            ),
            policy=AuthPolicyConfig(
                global_access_groups=_csv("MEMORY_MCP_AUTH_GLOBAL_ACCESS_GROUPS"),
                mutation_groups=_csv("MEMORY_MCP_AUTH_MUTATION_GROUPS"),
                sensitive_memory_groups=_csv("MEMORY_MCP_AUTH_SENSITIVE_GROUPS"),
                sensitive_echo_groups=_csv("MEMORY_MCP_AUTH_SENSITIVE_ECHO_GROUPS"),
                admin_groups=_csv("MEMORY_MCP_AUTH_ADMIN_GROUPS"),
                project_grants=_project_grants_from_env(),
            ),
        )
        config.validate()
        return config

    @classmethod
    def remote_for_tests(cls) -> Self:
        return cls(
            mode=AuthMode.REMOTE,
            oidc_issuer="https://idp.example.test",
            oidc_audience="memory-mcp",
            policy=AuthPolicyConfig(
                global_access_groups=frozenset({"readers", "svc-memory"}),
                mutation_groups=frozenset({"writers", "svc-memory"}),
                sensitive_memory_groups=frozenset({"sensitive-readers"}),
                sensitive_echo_groups=frozenset({"sensitive-echo"}),
                admin_groups=frozenset({"admins"}),
                project_grants=(
                    ProjectGrant(
                        project="memory-mcp",
                        groups=frozenset({"readers", "writers", "svc-memory", "sensitive-readers", "sensitive-echo"}),
                    ),
                ),
            ),
        )

    def validate(self) -> None:
        if self.mode == AuthMode.REMOTE and not self.trusted_proxy.enabled:
            if not self.oidc_issuer or not self.oidc_audience:
                raise ValueError("remote auth mode requires OIDC issuer/audience or trusted proxy configuration")


def _empty_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str) -> frozenset[str]:
    value = os.getenv(name, "")
    return frozenset(part.strip() for part in value.split(",") if part.strip())


def _project_grants_from_env() -> tuple[ProjectGrant, ...]:
    raw = os.getenv("MEMORY_MCP_AUTH_PROJECT_GRANTS_JSON", "").strip()
    if not raw:
        return ()
    decoded = json.loads(raw)
    if not isinstance(decoded, list):
        raise ValueError("MEMORY_MCP_AUTH_PROJECT_GRANTS_JSON must be a JSON list")
    grants = []
    for item in decoded:
        grants.append(
            ProjectGrant(
                project=item.get("project"),
                workspace=item.get("workspace"),
                component=item.get("component"),
                groups=frozenset(item.get("groups", [])),
                subjects=frozenset(item.get("subjects", [])),
            )
        )
    return tuple(grants)
