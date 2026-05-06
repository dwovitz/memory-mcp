"""add repo as first-class scope layer between project and component

Revision ID: 0005_repo_scope_layer
Revises: 0004_fix_schema_gap
Create Date: 2026-05-06 00:00:00.000000

Schema notes
------------
No DDL changes are required for the repo scope layer itself.

The ``applies_to`` JSONB column on ``memories`` (and other tables) already
stores arbitrary key/value pairs, so ``repo`` is written there by the
application layer without any column changes.

Index decision
--------------
Migration 0002_retrieval_indexes already created ``ix_memories_applies_to_gin``
— a full GIN index on ``memories.applies_to`` using ``jsonb_path_ops``.  That
index covers containment queries on *any* JSONB key, including the new ``repo``
field.  A separate composite functional index for ``(workspace, repo, project)``
would only help equality-filter queries on those three fields together, which is
not a current access pattern.  Adding it now would impose write overhead and
index-bloat with no measured benefit.  Revisit if query plans show sequential
scans on (workspace, repo, project) filter combinations.
"""

from __future__ import annotations

revision = "0005_repo_scope_layer"
down_revision = "0004_fix_schema_gap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No DDL changes — see module docstring for rationale.
    pass


def downgrade() -> None:
    # No DDL changes to revert.
    pass
