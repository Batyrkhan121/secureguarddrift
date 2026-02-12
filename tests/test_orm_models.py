# tests/test_orm_models.py
"""Tests for db.base and db.models — SQLAlchemy ORM layer."""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.models import (
    AuditLog,
    Edge,
    Node,
    Snapshot,
    Tenant,
    User,
)


@pytest.fixture()
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def async_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    yield engine
    asyncio.get_event_loop().run_until_complete(engine.dispose())


@pytest.fixture()
def session_factory(async_engine):
    return async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


def _run(coro):
    """Run an async coroutine synchronously in tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Metadata / schema tests
# ---------------------------------------------------------------------------

class TestModelMetadata:
    """Verify all 11 tables are registered in Base.metadata."""

    def test_all_tables_registered(self):
        expected = {
            "tenants", "users", "snapshots", "nodes", "edges",
            "drift_events", "policies", "feedback", "whitelist",
            "baselines", "audit_log",
        }
        actual = set(Base.metadata.tables.keys())
        assert expected == actual

    def test_table_count(self):
        assert len(Base.metadata.tables) == 11


class TestSchemaCreation:
    """Verify create_all generates all tables in async SQLite."""

    def test_create_all_async_sqlite(self):
        async def _test():
            engine = create_async_engine("sqlite+aiosqlite://", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with engine.connect() as conn:
                result = await conn.run_sync(
                    lambda c: c.execute(
                        text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                    ).fetchall()
                )
                tables = {row[0] for row in result}
            await engine.dispose()
            return tables

        tables = _run(_test())
        assert "tenants" in tables
        assert "snapshots" in tables
        assert "edges" in tables
        assert "nodes" in tables
        assert "drift_events" in tables
        assert "audit_log" in tables
        assert len(tables) == 11


class TestSnapshotRelationships:
    """Verify Snapshot → Node/Edge cascade relationships."""

    def test_snapshot_has_nodes_edges(self):
        assert hasattr(Snapshot, "nodes")
        assert hasattr(Snapshot, "edges")

    def test_node_has_snapshot_back_populates(self):
        assert hasattr(Node, "snapshot")

    def test_edge_has_snapshot_back_populates(self):
        assert hasattr(Edge, "snapshot")


class TestIndexes:
    """Verify key indexes are defined."""

    def test_snapshots_indexes(self):
        table = Base.metadata.tables["snapshots"]
        index_names = {idx.name for idx in table.indexes}
        assert "ix_snapshots_tenant_id" in index_names
        assert "ix_snapshots_timestamp_start" in index_names

    def test_edges_indexes(self):
        table = Base.metadata.tables["edges"]
        index_names = {idx.name for idx in table.indexes}
        assert "ix_edges_snapshot_id" in index_names
        assert "ix_edges_source" in index_names
        assert "ix_edges_source_dest" in index_names

    def test_drift_events_indexes(self):
        table = Base.metadata.tables["drift_events"]
        index_names = {idx.name for idx in table.indexes}
        assert "ix_drift_events_tenant_id" in index_names
        assert "ix_drift_events_severity" in index_names
        assert "ix_drift_events_status" in index_names

    def test_audit_log_indexes(self):
        table = Base.metadata.tables["audit_log"]
        index_names = {idx.name for idx in table.indexes}
        assert "ix_audit_log_tenant_id" in index_names
        assert "ix_audit_log_created_at" in index_names


class TestUniqueConstraints:
    """Verify unique constraints."""

    def test_whitelist_unique_constraint(self):
        table = Base.metadata.tables["whitelist"]
        uq_names = {c.name for c in table.constraints if hasattr(c, "columns") and len(c.columns) > 1}
        assert "uq_whitelist_tenant_src_dst" in uq_names

    def test_baseline_unique_constraint(self):
        table = Base.metadata.tables["baselines"]
        uq_names = {c.name for c in table.constraints if hasattr(c, "columns") and len(c.columns) > 1}
        assert "uq_baseline_tenant_src_dst" in uq_names


class TestCRUDOperations:
    """Verify basic CRUD with async SQLite session."""

    def test_insert_tenant_and_snapshot(self):
        async def _test():
            engine = create_async_engine("sqlite+aiosqlite://", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                tenant = Tenant(name="Test Corp", slug="test-corp")
                session.add(tenant)
                await session.flush()

                snap = Snapshot(
                    tenant_id=tenant.id,
                    timestamp_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    timestamp_end=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                )
                snap.nodes.append(Node(name="api-gw", namespace="default", node_type="gateway"))
                snap.edges.append(Edge(
                    source="api-gw", destination="order-svc",
                    request_count=100, error_count=2, error_rate=0.02,
                    avg_latency_ms=30.0, p99_latency_ms=55.0,
                ))
                session.add(snap)
                await session.commit()

                # Verify
                result = await session.get(Snapshot, snap.id)
                assert result is not None
                assert isinstance(result.id, uuid.UUID)
                assert result.tenant_id == tenant.id

            await engine.dispose()

        _run(_test())

    def test_insert_audit_log(self):
        async def _test():
            engine = create_async_engine("sqlite+aiosqlite://", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                log = AuditLog(
                    action="login",
                    resource_type="user",
                    ip_address="127.0.0.1",
                    details={"browser": "chrome"},
                )
                session.add(log)
                await session.commit()

                result = await session.get(AuditLog, log.id)
                assert result is not None
                assert result.action == "login"
                assert result.details == {"browser": "chrome"}

            await engine.dispose()

        _run(_test())

    def test_user_role_values(self):
        """Verify User model accepts valid roles."""
        async def _test():
            engine = create_async_engine("sqlite+aiosqlite://", echo=False)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
                tenant = Tenant(name="Acme", slug="acme")
                session.add(tenant)
                await session.flush()

                user = User(
                    tenant_id=tenant.id,
                    email="admin@acme.com",
                    password_hash="hashed",
                    role="admin",
                )
                session.add(user)
                await session.commit()

                result = await session.get(User, user.id)
                assert result.role == "admin"
                assert result.email == "admin@acme.com"

            await engine.dispose()

        _run(_test())
