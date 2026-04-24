"""Alembic migration environment."""

from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

from memory_mcp.config import load_database_config
from memory_mcp.db.connection import build_database_url
from memory_mcp.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTOGENERATE_IGNORED_INDEXES = {"ix_memories_full_text_search"}


def _include_object(
    object_: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Suppress known-safe autogenerate noise for hand-written expression indexes."""

    if type_ == "index" and name in AUTOGENERATE_IGNORED_INDEXES:
        return False
    return True


def _database_url() -> str:
    database_config = load_database_config(
        PROJECT_ROOT / ".env",
        require_env_file=True,
        require_values=True,
    )
    return build_database_url(database_config).render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    """Run migrations without an active DB connection."""

    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        include_object=_include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with an active DB connection."""

    config.set_main_option("sqlalchemy.url", _database_url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=_include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
