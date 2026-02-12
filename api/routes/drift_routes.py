# api/routes/drift_routes.py
# Роутер для drift-анализа

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from graph.models import Snapshot
from graph.storage import SnapshotStore
from drift.detector import detect_drift
from drift.scorer import score_all_events
from drift.explainer import explain_all
from db.base import get_db
from db.repository import DriftEventRepository
from api.routes import get_tenant_id

router = APIRouter(prefix="/api/drift", tags=["drift"])

_store: SnapshotStore | None = None


def init_store(s: SnapshotStore) -> None:
    global _store
    _store = s


def get_store() -> SnapshotStore:
    assert _store is not None, "Store not initialized"
    return _store


def _resolve_pair(
    store: SnapshotStore,
    baseline_id: Optional[str],
    current_id: Optional[str],
    tenant_id: str,
) -> tuple[Snapshot, Snapshot]:
    if baseline_id and current_id:
        b = store.load_snapshot(baseline_id, tenant_id=tenant_id)
        c = store.load_snapshot(current_id, tenant_id=tenant_id)
        if b is None or c is None:
            raise HTTPException(status_code=404, detail={"error": "Snapshot not found"})
        return b, c
    pair = store.get_latest_two(tenant_id=tenant_id)
    if pair is None:
        raise HTTPException(status_code=404, detail={"error": "Need at least 2 snapshots"})
    return pair


def _run_drift(baseline: Snapshot, current: Snapshot) -> dict:
    events = detect_drift(baseline, current)
    scored = score_all_events(events)
    cards = explain_all(scored)
    result = []
    for (ev, sc, sev), card in zip(scored, cards):
        result.append({
            "event_type": ev.event_type, "source": ev.source,
            "destination": ev.destination, "severity": ev.severity,
            "risk_score": sc, "title": card.title,
            "what_changed": card.what_changed, "why_risk": card.why_risk,
            "affected": card.affected, "recommendation": card.recommendation,
        })
    return {
        "baseline_id": baseline.snapshot_id,
        "current_id": current.snapshot_id,
        "events_count": len(result),
        "events": result,
    }


@router.get("/summary")
async def drift_summary(
    request: Request,
    baseline_id: Optional[str] = Query(None),
    current_id: Optional[str] = Query(None),
    store: SnapshotStore = Depends(get_store),
):
    tenant_id = get_tenant_id(request)
    baseline, current = _resolve_pair(store, baseline_id, current_id, tenant_id)
    events = detect_drift(baseline, current)
    scored = score_all_events(events)
    counts = {"total": len(scored), "critical": 0, "high": 0, "medium": 0, "low": 0}
    for _, _, sev in scored:
        if sev in counts:
            counts[sev] += 1
    return counts


@router.get("/summary/async")
async def drift_summary_async(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Async endpoint — drift event summary from ORM repository."""
    tenant_id = get_tenant_id(request)
    repo = DriftEventRepository(db)
    return await repo.get_summary(tenant_id or "default")


@router.get("/")
async def drift_analysis(
    request: Request,
    baseline_id: Optional[str] = Query(None),
    current_id: Optional[str] = Query(None),
    store: SnapshotStore = Depends(get_store),
):
    tenant_id = get_tenant_id(request)
    baseline, current = _resolve_pair(store, baseline_id, current_id, tenant_id)
    return _run_drift(baseline, current)


@router.get("/events/async")
async def drift_events_async(
    request: Request,
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Async endpoint — drift events from ORM repository."""
    tenant_id = get_tenant_id(request)
    repo = DriftEventRepository(db)
    events = await repo.get_events(
        tenant_id or "default", severity=severity, status=status, limit=limit,
    )
    return {"events": events, "events_count": len(events)}
