"""Tests for Alembic migration file correctness (no live DB required)."""

import importlib.util
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations" / "versions"


def _load_migration(filename: str):
    path = MIGRATIONS_DIR / filename
    spec = importlib.util.spec_from_file_location(filename.replace(".py", ""), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestMigration0006EmbeddingHnswIndex:
    def test_revision_id(self):
        m = _load_migration("0006_embedding_hnsw_index.py")
        assert m.revision == "0006_embedding_hnsw_index"

    def test_down_revision_chains_to_0005(self):
        m = _load_migration("0006_embedding_hnsw_index.py")
        assert m.down_revision == "0005_repo_scope_layer"

    def test_upgrade_is_callable(self):
        m = _load_migration("0006_embedding_hnsw_index.py")
        assert callable(m.upgrade)

    def test_downgrade_is_callable(self):
        m = _load_migration("0006_embedding_hnsw_index.py")
        assert callable(m.downgrade)

    def test_branch_labels_none(self):
        m = _load_migration("0006_embedding_hnsw_index.py")
        assert m.branch_labels is None

    def test_depends_on_none(self):
        m = _load_migration("0006_embedding_hnsw_index.py")
        assert m.depends_on is None
