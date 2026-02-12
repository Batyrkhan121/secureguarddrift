# db/migrations/versions/001_initial_schema.py
"""Initial schema: all 11 tables for SecureGuard Drift.

Revision ID: 001
Create Date: 2026-02-12
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("settings", sa.JSON, nullable=True),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'operator', 'viewer')", name="ck_user_role"),
    )

    # --- snapshots ---
    op.create_table(
        "snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("timestamp_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timestamp_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_", sa.JSON, nullable=True),
    )
    op.create_index("ix_snapshots_tenant_id", "snapshots", ["tenant_id"])
    op.create_index("ix_snapshots_timestamp_start", "snapshots", ["timestamp_start"])

    # --- nodes ---
    op.create_table(
        "nodes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(36), sa.ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("namespace", sa.String(255), server_default="default"),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("metadata_", sa.JSON, nullable=True),
    )

    # --- edges ---
    op.create_table(
        "edges",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(36), sa.ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("request_count", sa.Integer, nullable=False),
        sa.Column("error_count", sa.Integer, nullable=False),
        sa.Column("error_rate", sa.Float, nullable=False),
        sa.Column("avg_latency_ms", sa.Float, nullable=False),
        sa.Column("p99_latency_ms", sa.Float, nullable=False),
        sa.Column("metadata_", sa.JSON, nullable=True),
    )
    op.create_index("ix_edges_snapshot_id", "edges", ["snapshot_id"])
    op.create_index("ix_edges_source", "edges", ["source"])
    op.create_index("ix_edges_source_dest", "edges", ["source", "destination"])

    # --- drift_events ---
    op.create_table(
        "drift_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("baseline_id", sa.String(36), sa.ForeignKey("snapshots.id"), nullable=True),
        sa.Column("current_id", sa.String(36), sa.ForeignKey("snapshots.id"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("risk_score", sa.Integer, nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("what_changed", sa.Text, nullable=True),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("why_risk", sa.JSON, nullable=True),
        sa.Column("affected", sa.JSON, nullable=True),
        sa.Column("rules_triggered", sa.JSON, nullable=True),
        sa.Column("ml_modifiers", sa.JSON, nullable=True),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_drift_events_tenant_id", "drift_events", ["tenant_id"])
    op.create_index("ix_drift_events_severity", "drift_events", ["severity"])
    op.create_index("ix_drift_events_status", "drift_events", ["status"])

    # --- policies ---
    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("drift_event_id", sa.String(36), sa.ForeignKey("drift_events.id"), nullable=True),
        sa.Column("yaml_text", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("risk_score", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # --- feedback ---
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("drift_event_id", sa.String(36), sa.ForeignKey("drift_events.id"), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    # --- whitelist ---
    op.create_table(
        "whitelist",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "source", "destination", name="uq_whitelist_tenant_src_dst"),
    )

    # --- baselines ---
    op.create_table(
        "baselines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("mean_request_count", sa.Float, nullable=False),
        sa.Column("std_request_count", sa.Float, nullable=False),
        sa.Column("mean_error_rate", sa.Float, nullable=False),
        sa.Column("std_error_rate", sa.Float, nullable=False),
        sa.Column("mean_p99_latency", sa.Float, nullable=False),
        sa.Column("std_p99_latency", sa.Float, nullable=False),
        sa.Column("sample_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "source", "destination", name="uq_baseline_tenant_src_dst"),
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("baselines")
    op.drop_table("whitelist")
    op.drop_table("feedback")
    op.drop_table("policies")
    op.drop_table("drift_events")
    op.drop_table("edges")
    op.drop_table("nodes")
    op.drop_table("snapshots")
    op.drop_table("users")
    op.drop_table("tenants")
