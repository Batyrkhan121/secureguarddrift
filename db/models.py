# db/models.py
"""SQLAlchemy 2.0 ORM models for SecureGuard Drift.

Supports both PostgreSQL (primary) and SQLite (fallback) via type adapters.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator

from db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Portable types: UUID and JSONB with SQLite fallback
# ---------------------------------------------------------------------------


class GUID(TypeDecorator):
    """Platform-independent UUID type: PG native UUID, SQLite String(36)."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(str(value))
        return value


class PortableJSONB(TypeDecorator):
    """JSONB on PostgreSQL, plain JSON on SQLite."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB)
        return dialect.type_descriptor(JSON)


class PortableBigInteger(TypeDecorator):
    """BigInteger on PostgreSQL, Integer on SQLite (for autoincrement compat)."""

    impl = Integer
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(BigInteger())
        return dialect.type_descriptor(Integer())


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    settings: Mapped[dict | None] = mapped_column(PortableJSONB, default=dict)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (CheckConstraint("role IN ('admin', 'operator', 'viewer')", name="ck_user_role"),)


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("tenants.id"), nullable=False)
    timestamp_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timestamp_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    metadata_: Mapped[dict | None] = mapped_column("metadata_", PortableJSONB, nullable=True)

    nodes: Mapped[list[Node]] = relationship("Node", back_populates="snapshot", cascade="all, delete-orphan")
    edges: Mapped[list[Edge]] = relationship("Edge", back_populates="snapshot", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_snapshots_tenant_id", "tenant_id"),
        Index("ix_snapshots_timestamp_start", "timestamp_start"),
    )


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    namespace: Mapped[str] = mapped_column(String(255), default="default")
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata_", PortableJSONB, nullable=True)

    snapshot: Mapped[Snapshot] = relationship("Snapshot", back_populates="nodes")


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False)
    error_rate: Mapped[float] = mapped_column(Float, nullable=False)
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    p99_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata_", PortableJSONB, nullable=True)

    snapshot: Mapped[Snapshot] = relationship("Snapshot", back_populates="edges")

    __table_args__ = (
        Index("ix_edges_snapshot_id", "snapshot_id"),
        Index("ix_edges_source", "source"),
        Index("ix_edges_source_dest", "source", "destination"),
    )


class DriftEvent(Base):
    __tablename__ = "drift_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("tenants.id"), nullable=False)
    baseline_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("snapshots.id"), nullable=True)
    current_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("snapshots.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_changed: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_risk: Mapped[list | None] = mapped_column(PortableJSONB, nullable=True)
    affected: Mapped[list | None] = mapped_column(PortableJSONB, nullable=True)
    rules_triggered: Mapped[dict | None] = mapped_column(PortableJSONB, nullable=True)
    ml_modifiers: Mapped[dict | None] = mapped_column(PortableJSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_drift_events_tenant_id", "tenant_id"),
        Index("ix_drift_events_severity", "severity"),
        Index("ix_drift_events_status", "status"),
    )


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("tenants.id"), nullable=False)
    drift_event_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("drift_events.id"), nullable=True)
    yaml_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("tenants.id"), nullable=False)
    drift_event_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("drift_events.id"), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Whitelist(Base):
    __tablename__ = "whitelist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("tenants.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "source", "destination", name="uq_whitelist_tenant_src_dst"),)


class Baseline(Base):
    __tablename__ = "baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("tenants.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    mean_request_count: Mapped[float] = mapped_column(Float, nullable=False)
    std_request_count: Mapped[float] = mapped_column(Float, nullable=False)
    mean_error_rate: Mapped[float] = mapped_column(Float, nullable=False)
    std_error_rate: Mapped[float] = mapped_column(Float, nullable=False)
    mean_p99_latency: Mapped[float] = mapped_column(Float, nullable=False)
    std_p99_latency: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "source", "destination", name="uq_baseline_tenant_src_dst"),)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(PortableBigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict | None] = mapped_column(PortableJSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_audit_log_tenant_id", "tenant_id"),
        Index("ix_audit_log_created_at", "created_at"),
    )
