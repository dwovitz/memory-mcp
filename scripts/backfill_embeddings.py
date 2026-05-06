#!/usr/bin/env python3
"""Backfill embeddings for all active memories that have embedding IS NULL.

memory-mcp uses lazy embedding: embeddings are NOT computed at write time so
that the sentence-transformers dependency remains optional and writes stay fast.
Run this script after enabling MEMORY_MCP_EMBEDDING_ENABLED=true for the first
time, and again after any bulk ingest via scripts/ingest_workspace.py.

Usage:
    python scripts/backfill_embeddings.py [--batch-size N] [--dry-run]

Workflow:
    1. Run migrations (alembic upgrade head) to create the HNSW index.
    2. Set MEMORY_MCP_EMBEDDING_ENABLED=true and install extras:
           pip install memory-mcp[embedding]
    3. Run this script to populate embeddings for existing memories.
    4. For ongoing writes via add_memory, re-run periodically or after bulk ingests.

Environment variables:
    MEMORY_MCP_EMBEDDING_ENABLED   Must be "true" to proceed (default: false).
    MEMORY_MCP_EMBEDDING_MODEL     Model name (default: all-MiniLM-L6-v2).
    MEMORY_MCP_EMBEDDING_DIMENSIONS Dimensions (default: 384).
    DATABASE_URL                   SQLAlchemy-compatible PostgreSQL URL.
"""

from __future__ import annotations

import argparse
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill memory embeddings.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of memories to process per batch (default: 100).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without writing to the database.",
    )
    args = parser.parse_args()

    # Check embedding flag first — avoids importing heavy deps needlessly.
    enabled = os.getenv("MEMORY_MCP_EMBEDDING_ENABLED", "false").lower() == "true"
    if not enabled:
        print("MEMORY_MCP_EMBEDDING_ENABLED is not set to 'true'. Nothing to do.")
        sys.exit(0)

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from memory_mcp.embeddings.local_provider import LocalEmbeddingProvider
    from memory_mcp.embeddings.service import EmbeddingService

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    model_name = os.getenv("MEMORY_MCP_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    engine = create_engine(database_url)

    with Session(engine) as session:
        # Count total nulls.
        total_result = session.execute(
            text("SELECT COUNT(*) FROM memories WHERE embedding IS NULL AND status = 'active'")
        )
        total: int = total_result.scalar_one()

        if total == 0:
            print("No active memories with missing embeddings. Nothing to do.")
            return

        if args.dry_run:
            print(f"[dry-run] Would backfill {total} memories in batches of {args.batch_size}.")
            return

        provider = LocalEmbeddingProvider(model_name)
        service = EmbeddingService(provider, session)

        backfilled = 0
        while True:
            rows = session.execute(
                text(
                    "SELECT id, content FROM memories "
                    "WHERE embedding IS NULL AND status = 'active' "
                    "ORDER BY created_at "
                    "LIMIT :limit"
                ),
                {"limit": args.batch_size},
            ).fetchall()

            if not rows:
                break

            batch = [(row.id, row.content) for row in rows]
            service.embed_batch(batch)
            backfilled += len(batch)
            print(f"Backfilled {backfilled}/{total} memories")

        print(f"Done. Backfilled {backfilled} memories total.")


if __name__ == "__main__":
    main()
