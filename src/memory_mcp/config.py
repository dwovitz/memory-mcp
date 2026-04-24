"""Environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from dotenv import load_dotenv


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL connection settings."""

    host: str
    port: int
    database: str
    user: str
    password: str

    @classmethod
    def from_env(
        cls,
        env_file: str | Path | None = ".env",
        *,
        require_env_file: bool = False,
        require_values: bool = False,
    ) -> Self:
        if env_file is not None:
            env_path = Path(env_file)
            if require_env_file and not env_path.is_file():
                raise FileNotFoundError(f"Required environment file not found: {env_path}")
            load_dotenv(dotenv_path=env_path, override=False)

        if require_values:
            missing = [
                name
                for name in (
                    "POSTGRES_DB",
                    "POSTGRES_HOST",
                    "POSTGRES_PASSWORD",
                    "POSTGRES_PORT",
                    "POSTGRES_USER",
                )
                if not os.getenv(name)
            ]
            if missing:
                raise ValueError(
                    "Missing required database environment variables: "
                    + ", ".join(sorted(missing))
                )

        return cls(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=_read_int_env("POSTGRES_PORT", 5432),
            database=os.getenv("POSTGRES_DB", "memory_mcp"),
            user=os.getenv("POSTGRES_USER", "memory_mcp"),
            password=os.getenv("POSTGRES_PASSWORD", "memory_mcp_password"),
        )


def load_database_config(
    env_file: str | Path | None = ".env",
    *,
    require_env_file: bool = False,
    require_values: bool = False,
) -> DatabaseConfig:
    """Load PostgreSQL settings from environment variables and optional .env."""

    return DatabaseConfig.from_env(
        env_file=env_file,
        require_env_file=require_env_file,
        require_values=require_values,
    )


def _read_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
