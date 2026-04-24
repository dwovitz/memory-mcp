"""Run a minimal PostgreSQL connection check."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from memory_mcp.config import load_database_config
from memory_mcp.db import check_database_connection, create_db_engine


def main() -> int:
    config = load_database_config(
        REPO_ROOT / ".env",
        require_env_file=True,
        require_values=True,
    )
    engine = create_db_engine(config)

    try:
        result = check_database_connection(engine)
    finally:
        engine.dispose()

    print(
        "Connected to PostgreSQL "
        f"at {config.host}:{config.port}/{config.database}; SELECT 1 returned {result}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
