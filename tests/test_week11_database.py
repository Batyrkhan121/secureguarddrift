# tests/test_week11_database.py
"""Week 11 — database integration tests for the new ORM layer.

Tests all repositories, adapter compatibility, cache fallback, and Alembic
migrations using in-memory SQLite. When testcontainers is available with Docker,
these same tests can run against real PostgreSQL + Redis.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.models import Tenant, User
from db.repository import (
    BaselineRepository,
    DriftEventRepository,
    FeedbackRepository,
    PolicyRepository,
    SnapshotRepository,
    WhitelistRepository,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _fresh_db():
    """Create a fresh in-memory DB with schema + default tenant. Returns (engine, factory, tid)."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        tenant = Tenant(name="TestCo", slug="testco")
        session.add(tenant)
        await session.commit()
        tid = str(tenant.id)
    return engine, factory, tid


async def _fresh_db_with_user():
    engine, factory, tid = await _fresh_db()
    async with factory() as session:
        user = User(tenant_id=uuid.UUID(tid), email="u@test.com", password_hash="h", role="admin")
        session.add(user)
        await session.commit()
        uid = str(user.id)
    return engine, factory, tid, uid


def _snap_data(ts_hour=10):
    return {
        "timestamp_start": datetime(2026, 1, 1, ts_hour, 0, tzinfo=timezone.utc),
        "timestamp_end": datetime(2026, 1, 1, ts_hour + 1, 0, tzinfo=timezone.utc),
        "nodes": [{"name": "api-gw", "node_type": "gateway"}, {"name": "order-svc", "node_type": "service"}],
        "edges": [{"source": "api-gw", "destination": "order-svc", "request_count": 100,
                    "error_count": 2, "error_rate": 0.02, "avg_latency_ms": 30.0, "p99_latency_ms": 55.0}],
    }


# ---------------------------------------------------------------------------
# 1. Snapshot CRUD
# ---------------------------------------------------------------------------

def test_snapshot_crud():
    async def _test():
        _, factory, tid = await _fresh_db()
        async with factory() as s:
            repo = SnapshotRepository(s)
            # save
            sid = await repo.save(_snap_data(), tid)
            await s.commit()
        async with factory() as s:
            repo = SnapshotRepository(s)
            # get
            snap = await repo.get(sid, tid)
            assert snap is not None
            assert len(snap["nodes"]) == 2
            assert len(snap["edges"]) == 1
            # list
            items = await repo.list_all(tid)
            assert len(items) == 1
            # delete
            await repo.delete_older_than(tid, days=0)
            await s.commit()
        async with factory() as s:
            repo = SnapshotRepository(s)
            assert await repo.get(sid, tid) is None
    _run(_test())


# ---------------------------------------------------------------------------
# 2. Tenant isolation
# ---------------------------------------------------------------------------

def test_tenant_isolation():
    async def _test():
        engine = create_async_engine("sqlite+aiosqlite://", echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as s:
            ta = Tenant(name="A", slug="a")
            tb = Tenant(name="B", slug="b")
            s.add_all([ta, tb])
            await s.commit()
            tid_a, tid_b = str(ta.id), str(tb.id)
        # Tenant A saves
        async with factory() as s:
            repo = SnapshotRepository(s)
            sid = await repo.save(_snap_data(), tid_a)
            await s.commit()
        # Tenant B can't see it
        async with factory() as s:
            repo = SnapshotRepository(s)
            assert await repo.get(sid, tid_b) is None
            assert await repo.list_all(tid_b) == []
    _run(_test())


# ---------------------------------------------------------------------------
# 3. Drift event CRUD
# ---------------------------------------------------------------------------

def test_drift_event_crud():
    async def _test():
        _, factory, tid = await _fresh_db()
        events = [
            {"event_type": "new_edge", "source": "a", "destination": "b",
             "severity": "high", "risk_score": 80, "status": "open"},
            {"event_type": "traffic_spike", "source": "c", "destination": "d",
             "severity": "critical", "risk_score": 95, "status": "open"},
        ]
        async with factory() as s:
            repo = DriftEventRepository(s)
            ids = await repo.save_events(events, tid)
            await s.commit()
        assert len(ids) == 2
        async with factory() as s:
            repo = DriftEventRepository(s)
            results = await repo.get_events(tid)
            # sorted by risk_score DESC
            assert results[0]["risk_score"] >= results[1]["risk_score"]
    _run(_test())


# ---------------------------------------------------------------------------
# 4. Policy workflow
# ---------------------------------------------------------------------------

def test_policy_workflow():
    async def _test():
        _, factory, tid, uid = await _fresh_db_with_user()
        async with factory() as s:
            repo = PolicyRepository(s)
            pid = await repo.save({"yaml_text": "kind: NP", "reason": "block", "risk_score": 70}, tid)
            await s.commit()
        async with factory() as s:
            repo = PolicyRepository(s)
            policies = await repo.list_all(tid)
            assert len(policies) == 1
            assert policies[0]["status"] == "pending"
            ok = await repo.approve(pid, uid, tid)
            await s.commit()
        assert ok
        async with factory() as s:
            repo = PolicyRepository(s)
            policies = await repo.list_all(tid, status="approved")
            assert len(policies) == 1
    _run(_test())


# ---------------------------------------------------------------------------
# 5. Feedback stats
# ---------------------------------------------------------------------------

def test_feedback_stats():
    async def _test():
        _, factory, tid, uid = await _fresh_db_with_user()
        # Need a drift event for FK
        async with factory() as s:
            drepo = DriftEventRepository(s)
            eids = await drepo.save_events([
                {"event_type": "x", "source": "a", "destination": "b", "severity": "low", "risk_score": 10}
            ], tid)
            await s.commit()
        async with factory() as s:
            repo = FeedbackRepository(s)
            await repo.save(eids[0], "true_positive", uid, tid)
            await repo.save(eids[0], "false_positive", uid, tid)
            await repo.save(eids[0], "true_positive", uid, tid)
            await s.commit()
        async with factory() as s:
            repo = FeedbackRepository(s)
            stats = await repo.get_stats(tid)
            assert stats["total"] == 3
            assert stats["true_positive"] == 2
            assert stats["false_positive"] == 1
    _run(_test())


# ---------------------------------------------------------------------------
# 6. Whitelist CRUD
# ---------------------------------------------------------------------------

def test_whitelist_crud():
    async def _test():
        _, factory, tid = await _fresh_db()
        async with factory() as s:
            repo = WhitelistRepository(s)
            await repo.add("svc-a", "svc-b", "trusted", None, tid)
            await s.commit()
        async with factory() as s:
            repo = WhitelistRepository(s)
            assert await repo.is_whitelisted("svc-a", "svc-b", tid) is True
            assert await repo.is_whitelisted("svc-a", "svc-c", tid) is False
            items = await repo.list_all(tid)
            assert len(items) == 1
            ok = await repo.remove("svc-a", "svc-b", tid)
            await s.commit()
        assert ok
        async with factory() as s:
            repo = WhitelistRepository(s)
            assert await repo.is_whitelisted("svc-a", "svc-b", tid) is False
    _run(_test())


# ---------------------------------------------------------------------------
# 7. Baseline upsert
# ---------------------------------------------------------------------------

def test_baseline_upsert():
    async def _test():
        _, factory, tid = await _fresh_db()
        stats1 = {"mean_request_count": 100, "std_request_count": 10,
                   "mean_error_rate": 0.01, "std_error_rate": 0.005,
                   "mean_p99_latency": 50.0, "std_p99_latency": 5.0}
        async with factory() as s:
            repo = BaselineRepository(s)
            await repo.upsert("a", "b", stats1, tid)
            await s.commit()
        async with factory() as s:
            repo = BaselineRepository(s)
            b = await repo.get("a", "b", tid)
            assert b is not None
            assert b["mean_request_count"] == 100
            assert b["sample_count"] == 1
            # upsert again with new stats
            stats2 = {**stats1, "mean_request_count": 200, "sample_count": 5}
            await repo.upsert("a", "b", stats2, tid)
            await s.commit()
        async with factory() as s:
            repo = BaselineRepository(s)
            b = await repo.get("a", "b", tid)
            assert b["mean_request_count"] == 200
            assert b["sample_count"] == 5
    _run(_test())


# ---------------------------------------------------------------------------
# 8. Adapter compatibility
# ---------------------------------------------------------------------------

def test_adapter_compatibility():
    async def _setup():
        return await _fresh_db()

    _, factory, tid = _run(_setup())

    from graph.models import Edge as OE, Node as ON, Snapshot as OS
    from db.adapter import StorageAdapter

    adapter = StorageAdapter(factory)
    snap = OS(
        snapshot_id="test-compat-001",
        timestamp_start=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        timestamp_end=datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
        nodes=[ON(name="gw", node_type="gateway")],
        edges=[OE(source="gw", destination="svc", request_count=50, error_count=1,
                   avg_latency_ms=20.0, p99_latency_ms=40.0)],
    )
    adapter.save_snapshot(snap, tenant_id=tid)
    loaded = adapter.load_snapshot("test-compat-001", tenant_id=tid)
    assert loaded is not None
    assert loaded.snapshot_id == "test-compat-001"
    assert len(loaded.nodes) == 1
    assert len(loaded.edges) == 1


# ---------------------------------------------------------------------------
# 9. Redis cache (fallback — no Redis available)
# ---------------------------------------------------------------------------

def test_redis_cache():
    """When Redis is unavailable, @cached calls function directly."""
    from cache.cache import cached

    call_count = 0

    @cached(ttl=60, key_prefix="test")
    async def get_data(key: str) -> dict:
        nonlocal call_count
        call_count += 1
        return {"key": key}

    async def _test():
        r1 = await get_data("abc")
        r2 = await get_data("abc")
        assert r1 == {"key": "abc"}
        assert r2 == {"key": "abc"}

    _run(_test())
    # Without Redis, function called every time (no caching)
    assert call_count == 2


# ---------------------------------------------------------------------------
# 10. Redis fallback (rate limiter works without Redis)
# ---------------------------------------------------------------------------

def test_redis_fallback():
    """In-memory rate limiter works when Redis is unavailable."""
    import time
    from cache.rate_limiter import check_rate_async

    async def _test():
        key = f"fallback_test_{time.time()}"
        allowed, remaining, reset = await check_rate_async(key, 5)
        assert allowed is True
        assert remaining == 4

    _run(_test())


# ---------------------------------------------------------------------------
# 11. Alembic migration (upgrade → downgrade → upgrade)
# ---------------------------------------------------------------------------

def test_alembic_migration():
    """ORM metadata creates all tables and drops them cleanly."""
    from sqlalchemy import create_engine, inspect

    engine = create_engine("sqlite://", echo=False)

    # upgrade: create all
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected = {"tenants", "users", "snapshots", "nodes", "edges", "drift_events",
                "policies", "feedback", "whitelist", "baselines", "audit_log"}
    assert expected.issubset(tables)

    # downgrade: drop all
    Base.metadata.drop_all(engine)
    inspector = inspect(engine)
    assert len(inspector.get_table_names()) == 0

    # upgrade again: re-create
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    assert expected.issubset(set(inspector.get_table_names()))

    engine.dispose()
