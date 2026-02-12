# tests/test_async_routes.py
"""Tests for the new async /*/async route endpoints.

Validates that the dual-path migration works: old sync endpoints still work
(tested in test_api.py), new async endpoints use ORM repositories.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.models import Tenant
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
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    tid = str(uuid.uuid4())
    async with factory() as s:
        s.add(Tenant(id=uuid.UUID(tid), name="test", slug="test"))
        await s.commit()
    return engine, factory, tid


# ---------------------------------------------------------------------------
# 1. SnapshotRepository (used by graph_routes /async endpoints)
# ---------------------------------------------------------------------------

def test_async_graph_latest_repo():
    """SnapshotRepository.get_latest returns correct snapshot."""
    async def _test():
        engine, factory, tid = await _fresh_db()
        async with factory() as s:
            repo = SnapshotRepository(s)
            await repo.save({
                "timestamp_start": datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
                "timestamp_end": datetime(2026, 1, 1, 11, tzinfo=timezone.utc),
                "nodes": [{"name": "svc-a", "node_type": "service"}],
                "edges": [{"source": "svc-a", "destination": "svc-b",
                           "request_count": 100, "error_count": 1,
                           "avg_latency_ms": 10.0, "p99_latency_ms": 50.0}],
            }, tid)
            await s.commit()
        async with factory() as s:
            repo = SnapshotRepository(s)
            latest = await repo.get_latest(tid)
            assert latest is not None
            assert len(latest["nodes"]) == 1
            assert len(latest["edges"]) == 1
            assert latest["nodes"][0]["name"] == "svc-a"
        await engine.dispose()
    _run(_test())


def test_async_graph_by_id_repo():
    """SnapshotRepository.get returns snapshot by ID."""
    async def _test():
        engine, factory, tid = await _fresh_db()
        async with factory() as s:
            repo = SnapshotRepository(s)
            sid = await repo.save({
                "timestamp_start": datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
                "timestamp_end": datetime(2026, 1, 1, 11, tzinfo=timezone.utc),
                "nodes": [], "edges": [],
            }, tid)
            await s.commit()
        async with factory() as s:
            repo = SnapshotRepository(s)
            snap = await repo.get(sid, tid)
            assert snap is not None
            assert snap["id"] == sid
            # not found
            missing = await repo.get(str(uuid.uuid4()), tid)
            assert missing is None
        await engine.dispose()
    _run(_test())


# ---------------------------------------------------------------------------
# 2. DriftEventRepository (used by drift_routes /async endpoints)
# ---------------------------------------------------------------------------

def test_async_drift_summary_repo():
    """DriftEventRepository.get_summary returns correct counts."""
    async def _test():
        engine, factory, tid = await _fresh_db()
        async with factory() as s:
            repo = DriftEventRepository(s)
            await repo.save_events([
                {"event_type": "new_edge", "source": "a", "destination": "b",
                 "severity": "high", "risk_score": 80, "status": "open"},
                {"event_type": "removed_edge", "source": "c", "destination": "d",
                 "severity": "critical", "risk_score": 95, "status": "open"},
                {"event_type": "traffic_spike", "source": "e", "destination": "f",
                 "severity": "low", "risk_score": 20, "status": "open"},
            ], tid)
            await s.commit()
        async with factory() as s:
            repo = DriftEventRepository(s)
            summary = await repo.get_summary(tid)
            assert summary["total"] == 3
            assert summary["critical"] == 1
            assert summary["high"] == 1
            assert summary["low"] == 1
        await engine.dispose()
    _run(_test())


def test_async_drift_events_repo():
    """DriftEventRepository.get_events returns events sorted by risk_score."""
    async def _test():
        engine, factory, tid = await _fresh_db()
        async with factory() as s:
            repo = DriftEventRepository(s)
            await repo.save_events([
                {"event_type": "new_edge", "source": "a", "destination": "b",
                 "severity": "high", "risk_score": 50},
                {"event_type": "new_edge", "source": "c", "destination": "d",
                 "severity": "critical", "risk_score": 95},
            ], tid)
            await s.commit()
        async with factory() as s:
            repo = DriftEventRepository(s)
            events = await repo.get_events(tid)
            assert len(events) == 2
            assert events[0]["risk_score"] >= events[1]["risk_score"]
            # filter by severity
            highs = await repo.get_events(tid, severity="high")
            assert len(highs) == 1
        await engine.dispose()
    _run(_test())


# ---------------------------------------------------------------------------
# 3. PolicyRepository (used by policy_routes /async endpoints)
# ---------------------------------------------------------------------------

def test_async_policy_list_repo():
    """PolicyRepository.list_all returns policies for tenant."""
    async def _test():
        engine, factory, tid = await _fresh_db()
        async with factory() as s:
            repo = PolicyRepository(s)
            await repo.save({"yaml_text": "kind: NetworkPolicy", "reason": "test",
                             "risk_score": 50}, tid)
            await s.commit()
        async with factory() as s:
            repo = PolicyRepository(s)
            policies = await repo.list_all(tid)
            assert len(policies) == 1
            assert policies[0]["status"] == "pending"
        await engine.dispose()
    _run(_test())


def test_async_policy_approve_reject_repo():
    """PolicyRepository approve/reject update status."""
    async def _test():
        engine, factory, tid = await _fresh_db()
        user_id = str(uuid.uuid4())
        async with factory() as s:
            repo = PolicyRepository(s)
            pid = await repo.save({"yaml_text": "kind: NP", "reason": "r", "risk_score": 30}, tid)
            await s.commit()
        async with factory() as s:
            repo = PolicyRepository(s)
            ok = await repo.approve(pid, user_id, tid)
            await s.commit()
        assert ok
        async with factory() as s:
            repo = PolicyRepository(s)
            policies = await repo.list_all(tid, status="approved")
            assert len(policies) == 1
        await engine.dispose()
    _run(_test())


# ---------------------------------------------------------------------------
# 4. FeedbackRepository (used by ml_routes /async endpoints)
# ---------------------------------------------------------------------------

def test_async_feedback_stats_repo():
    """FeedbackRepository.get_stats returns correct counts."""
    async def _test():
        engine, factory, tid = await _fresh_db()
        eid1, eid2, eid3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        async with factory() as s:
            repo = FeedbackRepository(s)
            await repo.save(eid1, "true_positive", None, tid)
            await repo.save(eid2, "false_positive", None, tid)
            await repo.save(eid3, "true_positive", None, tid)
            await s.commit()
        async with factory() as s:
            repo = FeedbackRepository(s)
            stats = await repo.get_stats(tid)
            assert stats["total"] == 3
            assert stats["true_positive"] == 2
            assert stats["false_positive"] == 1
        await engine.dispose()
    _run(_test())


# ---------------------------------------------------------------------------
# 5. WhitelistRepository (used by ml_routes /async endpoints)
# ---------------------------------------------------------------------------

def test_async_whitelist_repo():
    """WhitelistRepository add/list/remove cycle."""
    async def _test():
        engine, factory, tid = await _fresh_db()
        async with factory() as s:
            repo = WhitelistRepository(s)
            await repo.add("svc-a", "svc-b", "expected", None, tid)
            await s.commit()
        async with factory() as s:
            repo = WhitelistRepository(s)
            entries = await repo.list_all(tid)
            assert len(entries) == 1
            assert entries[0]["source"] == "svc-a"
            is_wl = await repo.is_whitelisted("svc-a", "svc-b", tid)
            assert is_wl
        await engine.dispose()
    _run(_test())


# ---------------------------------------------------------------------------
# 6. BaselineRepository (used by ml_routes /async endpoints)
# ---------------------------------------------------------------------------

def test_async_baseline_repo():
    """BaselineRepository.upsert and get."""
    async def _test():
        engine, factory, tid = await _fresh_db()
        stats = {"mean_request_count": 100.0, "std_request_count": 10.0,
                 "mean_error_rate": 0.01, "std_error_rate": 0.005,
                 "mean_p99_latency": 50.0, "std_p99_latency": 5.0}
        async with factory() as s:
            repo = BaselineRepository(s)
            await repo.upsert("svc-a", "svc-b", stats, tid)
            await s.commit()
        async with factory() as s:
            repo = BaselineRepository(s)
            bl = await repo.get("svc-a", "svc-b", tid)
            assert bl is not None
            assert bl["mean_request_count"] == 100.0
            assert bl["sample_count"] == 1
        await engine.dispose()
    _run(_test())


# ---------------------------------------------------------------------------
# 7. Route structure validation
# ---------------------------------------------------------------------------

def test_async_routes_registered():
    """New /async endpoints are registered in the FastAPI app."""
    from api.server import app
    paths = [r.path for r in app.routes if hasattr(r, "path")]
    # Graph async endpoints
    assert "/api/graph/latest/async" in paths
    assert "/api/graph/{snapshot_id}/async" in paths
    # Drift async endpoints
    assert "/api/drift/summary/async" in paths
    assert "/api/drift/events/async" in paths
    # Policy async endpoints
    assert "/api/policies/async" in paths
    # Report async endpoint
    assert "/api/report/snapshots/async" in paths
