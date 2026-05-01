"""add security audit events

Revision ID: 0003_audit_events
Revises: 0002_retrieval_indexes
Create Date: 2026-05-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_audit_events"
down_revision = "0002_retrieval_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actor_subject", sa.String(length=255), nullable=True),
        sa.Column("actor_issuer", sa.String(length=512), nullable=True),
        sa.Column("principal_type", sa.String(length=64), nullable=True),
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_scope", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("decision IN ('allow', 'deny', 'success', 'failure')", name="ck_audit_events_decision"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_actor_subject", "audit_events", ["actor_subject"])
    op.create_index("ix_audit_events_tool_action", "audit_events", ["tool_name", "action"])
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index(
        "ix_audit_events_resource_scope_gin",
        "audit_events",
        ["resource_scope"],
        postgresql_using="gin",
        postgresql_ops={"resource_scope": "jsonb_path_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_resource_scope_gin", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_id", table_name="audit_events")
    op.drop_index("ix_audit_events_tool_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_subject", table_name="audit_events")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_table("audit_events")
