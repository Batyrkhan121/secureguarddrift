# tests/test_repository.py
"""Tests for db.repository — Repository pattern over ORM models."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.models import Tenant, User
from db.repository import (
    AuditRepository,
    BaselineRepository,
    DriftEventRepository,
    FeedbackRepository,
    PolicyRepository,
    SnapshotRepository,
    WhitelistRepository,
)


def _run(coro):
    """Run an async coroutine synchronously in tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _setup_db():
    """Create in-memory SQLite + schema + a default tenant. Returns (engine, session_factory, tenant_id)."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        tenant = Tenant(name="Test Corp", slug="test-corp")
        session.add(tenant)
        await session.commit()
        tid = str(tenant.id)
    return engine, factory, tid


async def _setup_with_user():
    """Setup DB + tenant + user."""
    engine, factory, tid = await _setup_db()
    async with factory() as session:
        user = User(tenant_id=uuid.UUID(tid), email="a@b.com", password_hash="x", role="admin")
        session.add(user)
        await session.commit()
        uid = str(user.id)
    return engine, factory, tid, uid


# ---------------------------------------------------------------------------
# SnapshotRepository
# ---------------------------------------------------------------------------

class TestSnapshotRepository:
    def test_save_and_get(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = SnapshotRepository(session)
                sid = await repo.save({
                    "timestamp_start": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    "timestamp_end": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                    "nodes": [{"name": "api-gw", "node_type": "gateway"}],
                    "edges": [{"source": "api-gw", "destination": "order-svc",
                               "request_count": 100, "error_count": 2,
                               "avg_latency_ms": 30.0, "p99_latency_ms": 55.0}],
                }, tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = SnapshotRepository(session)
                snap = await repo.get(sid, tenant_id=tid)
                assert snap is not None
                assert len(snap["nodes"]) == 1
                assert snap["nodes"][0]["name"] == "api-gw"
                assert len(snap["edges"]) == 1
                assert snap["edges"][0]["source"] == "api-gw"

            await engine.dispose()
        _run(_test())

    def test_get_wrong_tenant(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = SnapshotRepository(session)
                sid = await repo.save({
                    "timestamp_start": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    "timestamp_end": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                }, tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = SnapshotRepository(session)
                wrong = str(uuid.uuid4())
                result = await repo.get(sid, tenant_id=wrong)
                assert result is None
            await engine.dispose()
        _run(_test())

    def test_get_latest(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = SnapshotRepository(session)
                await repo.save({
                    "timestamp_start": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    "timestamp_end": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                }, tenant_id=tid)
                sid2 = await repo.save({
                    "timestamp_start": datetime(2026, 1, 2, tzinfo=timezone.utc),
                    "timestamp_end": datetime(2026, 1, 2, 1, tzinfo=timezone.utc),
                }, tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = SnapshotRepository(session)
                latest = await repo.get_latest(tid)
                assert latest is not None
                assert latest["id"] == sid2
            await engine.dispose()
        _run(_test())

    def test_list_all(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = SnapshotRepository(session)
                await repo.save({
                    "timestamp_start": datetime(2026, 1, 1, tzinfo=timezone.utc),
                    "timestamp_end": datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                }, tenant_id=tid)
                await repo.save({
                    "timestamp_start": datetime(2026, 1, 2, tzinfo=timezone.utc),
                    "timestamp_end": datetime(2026, 1, 2, 1, tzinfo=timezone.utc),
                }, tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = SnapshotRepository(session)
                result = await repo.list_all(tid)
                assert len(result) == 2
                assert "id" in result[0]
                assert "timestamp_start" in result[0]
            await engine.dispose()
        _run(_test())

    def test_delete_older_than(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            old = datetime(2020, 1, 1, tzinfo=timezone.utc)
            recent = datetime(2026, 1, 1, tzinfo=timezone.utc)
            async with factory() as session:
                repo = SnapshotRepository(session)
                await repo.save({"timestamp_start": old, "timestamp_end": old + timedelta(hours=1)}, tenant_id=tid)
                await repo.save({"timestamp_start": recent, "timestamp_end": recent + timedelta(hours=1)}, tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = SnapshotRepository(session)
                deleted = await repo.delete_older_than(tid, days=365)
                await session.commit()
                assert deleted >= 1

            async with factory() as session:
                repo = SnapshotRepository(session)
                remaining = await repo.list_all(tid)
                assert len(remaining) == 1
            await engine.dispose()
        _run(_test())


# ---------------------------------------------------------------------------
# DriftEventRepository
# ---------------------------------------------------------------------------

class TestDriftEventRepository:
    def test_save_and_get_events(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = DriftEventRepository(session)
                ids = await repo.save_events([{
                    "event_type": "new_edge", "source": "a", "destination": "b",
                    "severity": "high", "risk_score": 80,
                }], tenant_id=tid)
                await session.commit()
                assert len(ids) == 1

            async with factory() as session:
                repo = DriftEventRepository(session)
                events = await repo.get_events(tid)
                assert len(events) == 1
                assert events[0]["severity"] == "high"
            await engine.dispose()
        _run(_test())

    def test_get_summary(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = DriftEventRepository(session)
                await repo.save_events([
                    {"event_type": "x", "source": "a", "destination": "b", "severity": "critical", "risk_score": 90},
                    {"event_type": "y", "source": "c", "destination": "d", "severity": "high", "risk_score": 70},
                    {"event_type": "z", "source": "e", "destination": "f", "severity": "high", "risk_score": 60},
                ], tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = DriftEventRepository(session)
                s = await repo.get_summary(tid)
                assert s["total"] == 3
                assert s["critical"] == 1
                assert s["high"] == 2
            await engine.dispose()
        _run(_test())

    def test_update_status(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = DriftEventRepository(session)
                ids = await repo.save_events([{
                    "event_type": "x", "source": "a", "destination": "b",
                    "severity": "low", "risk_score": 10,
                }], tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = DriftEventRepository(session)
                ok = await repo.update_status(ids[0], "resolved", tid)
                await session.commit()
                assert ok is True

            async with factory() as session:
                repo = DriftEventRepository(session)
                events = await repo.get_events(tid, status="resolved")
                assert len(events) == 1
            await engine.dispose()
        _run(_test())

    def test_update_status_wrong_tenant(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = DriftEventRepository(session)
                ids = await repo.save_events([{
                    "event_type": "x", "source": "a", "destination": "b",
                    "severity": "low", "risk_score": 10,
                }], tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = DriftEventRepository(session)
                ok = await repo.update_status(ids[0], "resolved", str(uuid.uuid4()))
                assert ok is False
            await engine.dispose()
        _run(_test())


# ---------------------------------------------------------------------------
# PolicyRepository
# ---------------------------------------------------------------------------

class TestPolicyRepository:
    def test_save_and_list(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = PolicyRepository(session)
                pid = await repo.save({
                    "yaml_text": "apiVersion: v1", "reason": "block new edge",
                    "risk_score": 75,
                }, tenant_id=tid)
                await session.commit()
                assert pid

            async with factory() as session:
                repo = PolicyRepository(session)
                policies = await repo.list_all(tid)
                assert len(policies) == 1
                assert policies[0]["status"] == "pending"
            await engine.dispose()
        _run(_test())

    def test_approve_and_reject(self):
        async def _test():
            engine, factory, tid, uid = await _setup_with_user()
            async with factory() as session:
                repo = PolicyRepository(session)
                pid1 = await repo.save({"yaml_text": "v1", "reason": "r1", "risk_score": 50}, tenant_id=tid)
                pid2 = await repo.save({"yaml_text": "v2", "reason": "r2", "risk_score": 60}, tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = PolicyRepository(session)
                assert await repo.approve(pid1, uid, tid) is True
                assert await repo.reject(pid2, uid, tid) is True
                await session.commit()

            async with factory() as session:
                repo = PolicyRepository(session)
                approved = await repo.list_all(tid, status="approved")
                rejected = await repo.list_all(tid, status="rejected")
                assert len(approved) == 1
                assert len(rejected) == 1
            await engine.dispose()
        _run(_test())

    def test_get_yaml(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = PolicyRepository(session)
                pid = await repo.save({
                    "yaml_text": "kind: NetworkPolicy", "reason": "test", "risk_score": 50,
                }, tenant_id=tid)
                await session.commit()

            async with factory() as session:
                repo = PolicyRepository(session)
                yaml = await repo.get_yaml(pid, tid)
                assert yaml == "kind: NetworkPolicy"
                # Wrong tenant
                none_yaml = await repo.get_yaml(pid, str(uuid.uuid4()))
                assert none_yaml is None
            await engine.dispose()
        _run(_test())


# ---------------------------------------------------------------------------
# WhitelistRepository
# ---------------------------------------------------------------------------

class TestWhitelistRepository:
    def test_add_list_remove(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = WhitelistRepository(session)
                await repo.add("svc-a", "svc-b", "safe connection", None, tid)
                await session.commit()

            async with factory() as session:
                repo = WhitelistRepository(session)
                entries = await repo.list_all(tid)
                assert len(entries) == 1
                assert entries[0]["source"] == "svc-a"

            async with factory() as session:
                repo = WhitelistRepository(session)
                ok = await repo.remove("svc-a", "svc-b", tid)
                await session.commit()
                assert ok is True

            async with factory() as session:
                repo = WhitelistRepository(session)
                entries = await repo.list_all(tid)
                assert len(entries) == 0
            await engine.dispose()
        _run(_test())

    def test_is_whitelisted(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = WhitelistRepository(session)
                await repo.add("svc-a", "svc-b", "ok", None, tid)
                await session.commit()

            async with factory() as session:
                repo = WhitelistRepository(session)
                assert await repo.is_whitelisted("svc-a", "svc-b", tid) is True
                assert await repo.is_whitelisted("svc-x", "svc-y", tid) is False
            await engine.dispose()
        _run(_test())


# ---------------------------------------------------------------------------
# BaselineRepository
# ---------------------------------------------------------------------------

class TestBaselineRepository:
    def test_upsert_and_get(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            stats = {
                "mean_request_count": 100.0, "std_request_count": 10.0,
                "mean_error_rate": 0.01, "std_error_rate": 0.005,
                "mean_p99_latency": 50.0, "std_p99_latency": 5.0,
            }
            async with factory() as session:
                repo = BaselineRepository(session)
                await repo.upsert("svc-a", "svc-b", stats, tid)
                await session.commit()

            async with factory() as session:
                repo = BaselineRepository(session)
                b = await repo.get("svc-a", "svc-b", tid)
                assert b is not None
                assert b["mean_request_count"] == 100.0
                assert b["sample_count"] == 1

            # Upsert again (update)
            stats["mean_request_count"] = 200.0
            stats["sample_count"] = 5
            async with factory() as session:
                repo = BaselineRepository(session)
                await repo.upsert("svc-a", "svc-b", stats, tid)
                await session.commit()

            async with factory() as session:
                repo = BaselineRepository(session)
                b = await repo.get("svc-a", "svc-b", tid)
                assert b["mean_request_count"] == 200.0
                assert b["sample_count"] == 5
            await engine.dispose()
        _run(_test())

    def test_get_not_found(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = BaselineRepository(session)
                b = await repo.get("x", "y", tid)
                assert b is None
            await engine.dispose()
        _run(_test())


# ---------------------------------------------------------------------------
# AuditRepository
# ---------------------------------------------------------------------------

class TestAuditRepository:
    def test_log_and_query(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = AuditRepository(session)
                await repo.log(tid, None, "login", resource_type="user", details={"ip": "1.2.3.4"})
                await repo.log(tid, None, "create_policy", resource_type="policy")
                await session.commit()

            async with factory() as session:
                repo = AuditRepository(session)
                logs = await repo.query(tid)
                assert len(logs) == 2

                logs_filtered = await repo.query(tid, action="login")
                assert len(logs_filtered) == 1
                assert logs_filtered[0]["action"] == "login"
            await engine.dispose()
        _run(_test())

    def test_query_no_tenant(self):
        """Super-admin can query without tenant filter."""
        async def _test():
            engine, factory, tid = await _setup_db()
            async with factory() as session:
                repo = AuditRepository(session)
                await repo.log(tid, None, "login")
                await repo.log(None, None, "system_start")
                await session.commit()

            async with factory() as session:
                repo = AuditRepository(session)
                all_logs = await repo.query(None)
                assert len(all_logs) == 2
            await engine.dispose()
        _run(_test())


# ---------------------------------------------------------------------------
# FeedbackRepository
# ---------------------------------------------------------------------------

class TestFeedbackRepository:
    def test_save_and_stats(self):
        async def _test():
            engine, factory, tid = await _setup_db()
            # Need a drift event for FK
            async with factory() as session:
                drift_repo = DriftEventRepository(session)
                ids = await drift_repo.save_events([{
                    "event_type": "new_edge", "source": "a", "destination": "b",
                    "severity": "high", "risk_score": 80,
                }], tenant_id=tid)
                await session.commit()
                eid = ids[0]

            async with factory() as session:
                repo = FeedbackRepository(session)
                fb_id = await repo.save(eid, "true_positive", None, tid, comment="looks right")
                await session.commit()
                assert fb_id is not None

            async with factory() as session:
                repo = FeedbackRepository(session)
                stats = await repo.get_stats(tid)
                assert stats["total"] == 1
                assert stats.get("true_positive", 0) == 1
            await engine.dispose()
        _run(_test())
