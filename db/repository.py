# db/repository.py
"""Repository pattern for async data access over SQLAlchemy ORM models.

Every repository receives an AsyncSession and never creates its own.
All SELECT queries filter by tenant_id for data isolation.
All methods return plain dicts (not ORM objects) for easy serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    AuditLog,
    Baseline,
    DriftEvent,
    Edge,
    Feedback,
    Node,
    Policy,
    Snapshot,
    Whitelist,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# SnapshotRepository
# ---------------------------------------------------------------------------

class SnapshotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, snapshot_data: dict, tenant_id: str) -> str:
        """Save snapshot with nodes and edges. Returns snapshot_id."""
        snap_id = snapshot_data.get("id") or _uuid()
        snap = Snapshot(
            id=uuid.UUID(str(snap_id)),
            tenant_id=uuid.UUID(str(tenant_id)),
            timestamp_start=snapshot_data["timestamp_start"],
            timestamp_end=snapshot_data["timestamp_end"],
            metadata_=snapshot_data.get("metadata_"),
        )
        for n in snapshot_data.get("nodes", []):
            snap.nodes.append(Node(
                name=n["name"],
                namespace=n.get("namespace", "default"),
                node_type=n["node_type"],
                metadata_=n.get("metadata_"),
            ))
        for e in snapshot_data.get("edges", []):
            snap.edges.append(Edge(
                source=e["source"],
                destination=e["destination"],
                request_count=e["request_count"],
                error_count=e["error_count"],
                error_rate=e.get("error_rate", 0.0),
                avg_latency_ms=e["avg_latency_ms"],
                p99_latency_ms=e["p99_latency_ms"],
                metadata_=e.get("metadata_"),
            ))
        self.session.add(snap)
        await self.session.flush()
        return str(snap.id)

    async def get(self, snapshot_id: str, tenant_id: str) -> dict | None:
        """Get snapshot with nodes and edges."""
        stmt = (
            select(Snapshot)
            .options(selectinload(Snapshot.nodes), selectinload(Snapshot.edges))
            .where(Snapshot.id == uuid.UUID(str(snapshot_id)), Snapshot.tenant_id == uuid.UUID(str(tenant_id)))
        )
        result = await self.session.execute(stmt)
        snap = result.scalar_one_or_none()
        if snap is None:
            return None
        return self._to_dict(snap)

    async def get_latest(self, tenant_id: str) -> dict | None:
        """Get most recent snapshot for tenant."""
        stmt = (
            select(Snapshot)
            .options(selectinload(Snapshot.nodes), selectinload(Snapshot.edges))
            .where(Snapshot.tenant_id == uuid.UUID(str(tenant_id)))
            .order_by(Snapshot.timestamp_start.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        snap = result.scalar_one_or_none()
        return self._to_dict(snap) if snap else None

    async def list_all(self, tenant_id: str, limit: int = 50) -> list[dict]:
        """List snapshots for tenant (metadata only, no nodes/edges)."""
        stmt = (
            select(Snapshot)
            .where(Snapshot.tenant_id == uuid.UUID(str(tenant_id)))
            .order_by(Snapshot.timestamp_start.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            {"id": str(s.id), "timestamp_start": s.timestamp_start.isoformat(),
             "timestamp_end": s.timestamp_end.isoformat(), "created_at": s.created_at.isoformat() if s.created_at else None,
             "metadata_": s.metadata_}
            for s in result.scalars().all()
        ]

    async def delete_older_than(self, tenant_id: str, days: int) -> int:
        """Delete snapshots older than N days. Returns count deleted."""
        cutoff = _utcnow() - timedelta(days=days)
        stmt = (
            delete(Snapshot)
            .where(Snapshot.tenant_id == uuid.UUID(str(tenant_id)), Snapshot.timestamp_start < cutoff)
        )
        result = await self.session.execute(stmt)
        return result.rowcount

    @staticmethod
    def _to_dict(snap: Snapshot) -> dict:
        return {
            "id": str(snap.id),
            "tenant_id": str(snap.tenant_id),
            "timestamp_start": snap.timestamp_start.isoformat(),
            "timestamp_end": snap.timestamp_end.isoformat(),
            "created_at": snap.created_at.isoformat() if snap.created_at else None,
            "metadata_": snap.metadata_,
            "nodes": [{"name": n.name, "namespace": n.namespace, "node_type": n.node_type} for n in snap.nodes],
            "edges": [
                {"source": e.source, "destination": e.destination, "request_count": e.request_count,
                 "error_count": e.error_count, "error_rate": e.error_rate,
                 "avg_latency_ms": e.avg_latency_ms, "p99_latency_ms": e.p99_latency_ms}
                for e in snap.edges
            ],
        }


# ---------------------------------------------------------------------------
# DriftEventRepository
# ---------------------------------------------------------------------------

class DriftEventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_events(self, events: list[dict], tenant_id: str) -> list[str]:
        """Bulk save drift events. Returns list of event_ids."""
        tid = uuid.UUID(str(tenant_id))
        objs = []
        ids = []
        for e in events:
            eid = e.get("id") or _uuid()
            ids.append(str(eid))
            objs.append(DriftEvent(
                id=uuid.UUID(str(eid)), tenant_id=tid,
                baseline_id=uuid.UUID(str(e["baseline_id"])) if e.get("baseline_id") else None,
                current_id=uuid.UUID(str(e["current_id"])) if e.get("current_id") else None,
                event_type=e["event_type"], source=e["source"], destination=e["destination"],
                severity=e["severity"], risk_score=e["risk_score"],
                title=e.get("title"), what_changed=e.get("what_changed"),
                recommendation=e.get("recommendation"), why_risk=e.get("why_risk"),
                affected=e.get("affected"), rules_triggered=e.get("rules_triggered"),
                ml_modifiers=e.get("ml_modifiers"), status=e.get("status", "open"),
            ))
        self.session.add_all(objs)
        await self.session.flush()
        return ids

    async def get_events(self, tenant_id: str, *, baseline_id: str | None = None,
                         current_id: str | None = None, severity: str | None = None,
                         status: str | None = None, limit: int = 100) -> list[dict]:
        """Get drift events with optional filters. Sorted by risk_score DESC."""
        stmt = select(DriftEvent).where(DriftEvent.tenant_id == uuid.UUID(str(tenant_id)))
        if baseline_id:
            stmt = stmt.where(DriftEvent.baseline_id == uuid.UUID(str(baseline_id)))
        if current_id:
            stmt = stmt.where(DriftEvent.current_id == uuid.UUID(str(current_id)))
        if severity:
            stmt = stmt.where(DriftEvent.severity == severity)
        if status:
            stmt = stmt.where(DriftEvent.status == status)
        stmt = stmt.order_by(DriftEvent.risk_score.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return [
            {"id": str(ev.id), "event_type": ev.event_type, "source": ev.source,
             "destination": ev.destination, "severity": ev.severity, "risk_score": ev.risk_score,
             "title": ev.title, "status": ev.status, "created_at": ev.created_at.isoformat() if ev.created_at else None}
            for ev in result.scalars().all()
        ]

    async def get_summary(self, tenant_id: str) -> dict:
        """Count events by severity."""
        tid = uuid.UUID(str(tenant_id))
        stmt = (
            select(DriftEvent.severity, func.count())
            .where(DriftEvent.tenant_id == tid)
            .group_by(DriftEvent.severity)
        )
        result = await self.session.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}
        total = sum(counts.values())
        return {"total": total, "critical": counts.get("critical", 0), "high": counts.get("high", 0),
                "medium": counts.get("medium", 0), "low": counts.get("low", 0)}

    async def update_status(self, event_id: str, status: str, tenant_id: str) -> bool:
        """Update event status. Returns False if not found/wrong tenant."""
        stmt = (
            update(DriftEvent)
            .where(DriftEvent.id == uuid.UUID(str(event_id)), DriftEvent.tenant_id == uuid.UUID(str(tenant_id)))
            .values(status=status)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0


# ---------------------------------------------------------------------------
# PolicyRepository
# ---------------------------------------------------------------------------

class PolicyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, policy_data: dict, tenant_id: str) -> str:
        """Save a policy. Returns policy_id."""
        pid = policy_data.get("id") or _uuid()
        p = Policy(
            id=uuid.UUID(str(pid)), tenant_id=uuid.UUID(str(tenant_id)),
            drift_event_id=uuid.UUID(str(policy_data["drift_event_id"])) if policy_data.get("drift_event_id") else None,
            yaml_text=policy_data["yaml_text"], reason=policy_data["reason"],
            risk_score=policy_data["risk_score"], status=policy_data.get("status", "pending"),
        )
        self.session.add(p)
        await self.session.flush()
        return str(p.id)

    async def list_all(self, tenant_id: str, status: str | None = None) -> list[dict]:
        stmt = select(Policy).where(Policy.tenant_id == uuid.UUID(str(tenant_id)))
        if status:
            stmt = stmt.where(Policy.status == status)
        stmt = stmt.order_by(Policy.created_at.desc())
        result = await self.session.execute(stmt)
        return [
            {"id": str(p.id), "reason": p.reason, "risk_score": p.risk_score,
             "status": p.status, "created_at": p.created_at.isoformat() if p.created_at else None}
            for p in result.scalars().all()
        ]

    async def approve(self, policy_id: str, user_id: str, tenant_id: str) -> bool:
        stmt = (
            update(Policy)
            .where(Policy.id == uuid.UUID(str(policy_id)), Policy.tenant_id == uuid.UUID(str(tenant_id)))
            .values(status="approved", approved_by=uuid.UUID(str(user_id)), applied_at=_utcnow())
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def reject(self, policy_id: str, user_id: str, tenant_id: str) -> bool:
        stmt = (
            update(Policy)
            .where(Policy.id == uuid.UUID(str(policy_id)), Policy.tenant_id == uuid.UUID(str(tenant_id)))
            .values(status="rejected", approved_by=uuid.UUID(str(user_id)))
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_yaml(self, policy_id: str, tenant_id: str) -> str | None:
        stmt = select(Policy.yaml_text).where(
            Policy.id == uuid.UUID(str(policy_id)), Policy.tenant_id == uuid.UUID(str(tenant_id))
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return row


# ---------------------------------------------------------------------------
# FeedbackRepository
# ---------------------------------------------------------------------------

class FeedbackRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, event_id: str, verdict: str, user_id: str | None, tenant_id: str,
                   comment: str | None = None) -> int:
        fb = Feedback(
            tenant_id=uuid.UUID(str(tenant_id)),
            drift_event_id=uuid.UUID(str(event_id)) if event_id else None,
            user_id=uuid.UUID(str(user_id)) if user_id else None,
            verdict=verdict, comment=comment,
        )
        self.session.add(fb)
        await self.session.flush()
        return fb.id

    async def get_stats(self, tenant_id: str) -> dict:
        tid = uuid.UUID(str(tenant_id))
        stmt = select(Feedback.verdict, func.count()).where(Feedback.tenant_id == tid).group_by(Feedback.verdict)
        result = await self.session.execute(stmt)
        counts = {row[0]: row[1] for row in result.all()}
        return {"total": sum(counts.values()), **counts}

    async def get_for_edge(self, source: str, dest: str, tenant_id: str) -> list[dict]:
        stmt = (
            select(Feedback)
            .join(DriftEvent, Feedback.drift_event_id == DriftEvent.id)
            .where(Feedback.tenant_id == uuid.UUID(str(tenant_id)),
                   DriftEvent.source == source, DriftEvent.destination == dest)
            .order_by(Feedback.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [
            {"id": fb.id, "verdict": fb.verdict, "comment": fb.comment,
             "created_at": fb.created_at.isoformat() if fb.created_at else None}
            for fb in result.scalars().all()
        ]


# ---------------------------------------------------------------------------
# WhitelistRepository
# ---------------------------------------------------------------------------

class WhitelistRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, source: str, dest: str, reason: str | None,
                  user_id: str | None, tenant_id: str, expires_at: datetime | None = None) -> int:
        w = Whitelist(
            tenant_id=uuid.UUID(str(tenant_id)), source=source, destination=dest,
            reason=reason, created_by=uuid.UUID(str(user_id)) if user_id else None,
            expires_at=expires_at,
        )
        self.session.add(w)
        await self.session.flush()
        return w.id

    async def remove(self, source: str, dest: str, tenant_id: str) -> bool:
        stmt = delete(Whitelist).where(
            Whitelist.tenant_id == uuid.UUID(str(tenant_id)),
            Whitelist.source == source, Whitelist.destination == dest,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def list_all(self, tenant_id: str) -> list[dict]:
        stmt = select(Whitelist).where(Whitelist.tenant_id == uuid.UUID(str(tenant_id))).order_by(Whitelist.created_at.desc())
        result = await self.session.execute(stmt)
        return [
            {"id": w.id, "source": w.source, "destination": w.destination,
             "reason": w.reason, "expires_at": w.expires_at.isoformat() if w.expires_at else None,
             "created_at": w.created_at.isoformat() if w.created_at else None}
            for w in result.scalars().all()
        ]

    async def is_whitelisted(self, source: str, dest: str, tenant_id: str) -> bool:
        now = _utcnow()
        stmt = select(Whitelist).where(
            Whitelist.tenant_id == uuid.UUID(str(tenant_id)),
            Whitelist.source == source, Whitelist.destination == dest,
        )
        result = await self.session.execute(stmt)
        w = result.scalar_one_or_none()
        if w is None:
            return False
        if w.expires_at and w.expires_at < now:
            return False
        return True


# ---------------------------------------------------------------------------
# BaselineRepository
# ---------------------------------------------------------------------------

class BaselineRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, source: str, dest: str, stats: dict, tenant_id: str) -> None:
        tid = uuid.UUID(str(tenant_id))
        stmt = select(Baseline).where(
            Baseline.tenant_id == tid, Baseline.source == source, Baseline.destination == dest
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.mean_request_count = stats["mean_request_count"]
            existing.std_request_count = stats["std_request_count"]
            existing.mean_error_rate = stats["mean_error_rate"]
            existing.std_error_rate = stats["std_error_rate"]
            existing.mean_p99_latency = stats["mean_p99_latency"]
            existing.std_p99_latency = stats["std_p99_latency"]
            existing.sample_count = stats.get("sample_count", existing.sample_count + 1)
            existing.updated_at = _utcnow()
        else:
            self.session.add(Baseline(
                tenant_id=tid, source=source, destination=dest,
                mean_request_count=stats["mean_request_count"], std_request_count=stats["std_request_count"],
                mean_error_rate=stats["mean_error_rate"], std_error_rate=stats["std_error_rate"],
                mean_p99_latency=stats["mean_p99_latency"], std_p99_latency=stats["std_p99_latency"],
                sample_count=stats.get("sample_count", 1),
            ))
        await self.session.flush()

    async def get(self, source: str, dest: str, tenant_id: str) -> dict | None:
        stmt = select(Baseline).where(
            Baseline.tenant_id == uuid.UUID(str(tenant_id)),
            Baseline.source == source, Baseline.destination == dest,
        )
        result = await self.session.execute(stmt)
        b = result.scalar_one_or_none()
        if b is None:
            return None
        return {
            "source": b.source, "destination": b.destination,
            "mean_request_count": b.mean_request_count, "std_request_count": b.std_request_count,
            "mean_error_rate": b.mean_error_rate, "std_error_rate": b.std_error_rate,
            "mean_p99_latency": b.mean_p99_latency, "std_p99_latency": b.std_p99_latency,
            "sample_count": b.sample_count, "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        }


# ---------------------------------------------------------------------------
# AuditRepository
# ---------------------------------------------------------------------------

class AuditRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, tenant_id: str | None, user_id: str | None, action: str,
                  resource_type: str | None = None, resource_id: str | None = None,
                  details: dict | None = None, ip: str | None = None) -> None:
        self.session.add(AuditLog(
            tenant_id=uuid.UUID(str(tenant_id)) if tenant_id else None,
            user_id=uuid.UUID(str(user_id)) if user_id else None,
            action=action, resource_type=resource_type, resource_id=resource_id,
            details=details, ip_address=ip,
        ))
        await self.session.flush()

    async def query(self, tenant_id: str | None, limit: int = 100,
                    action: str | None = None) -> list[dict]:
        stmt = select(AuditLog)
        if tenant_id:
            stmt = stmt.where(AuditLog.tenant_id == uuid.UUID(str(tenant_id)))
        if action:
            stmt = stmt.where(AuditLog.action == action)
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return [
            {"id": a.id, "action": a.action, "resource_type": a.resource_type,
             "resource_id": a.resource_id, "details": a.details, "ip_address": a.ip_address,
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in result.scalars().all()
        ]
