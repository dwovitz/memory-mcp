"""Reusable PostgreSQL connection utilities."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.orm import Session, sessionmaker

from memory_mcp.config import DatabaseConfig, load_database_config

_ENGINE: Engine | None = None
_SESSION_FACTORY: sessionmaker[Session] | None = None
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def build_database_url(config: DatabaseConfig) -> URL:
    """Build a SQLAlchemy URL without exposing credentials in logs by default."""

    return URL.create(
        drivername="postgresql+psycopg",
        username=config.user,
        password=config.password,
        host=config.host,
        port=config.port,
        database=config.database,
    )


def create_db_engine(config: DatabaseConfig | None = None) -> Engine:
    """Create a SQLAlchemy engine for PostgreSQL."""

    resolved_config = config or load_runtime_database_config()
    return create_engine(build_database_url(resolved_config), pool_pre_ping=True)


def load_runtime_database_config() -> DatabaseConfig:
    """Load runtime DB config and fail fast if it is missing or incomplete."""

    env_file = Path(os.getenv("MEMORY_MCP_ENV_FILE", PROJECT_ROOT / ".env"))
    return load_database_config(
        env_file,
        require_env_file=True,
        require_values=True,
    )


def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine."""

    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_db_engine()
    return _ENGINE


def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide SQLAlchemy session factory."""

    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        _SESSION_FACTORY = sessionmaker(bind=get_engine(), autoflush=False)
    return _SESSION_FACTORY


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional SQLAlchemy session scope."""

    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database_connection(engine: Engine | None = None) -> int:
    """Run a minimal connection check."""

    resolved_engine = engine or get_engine()
    with resolved_engine.connect() as connection:
        return connection.execute(text("SELECT 1")).scalar_one()
