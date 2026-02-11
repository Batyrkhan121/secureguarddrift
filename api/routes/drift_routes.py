# api/routes/drift_routes.py
# Роутер для drift-анализа

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from graph.models import Snapshot
from graph.storage import SnapshotStore
from drift.detector import detect_drift
from drift.scorer import score_all_events
from drift.explainer import explain_all

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
) -> tuple[Snapshot, Snapshot]:
    if baseline_id and current_id:
        b = store.load_snapshot(baseline_id)
        c = store.load_snapshot(current_id)
        if b is None or c is None:
            raise HTTPException(status_code=404, detail={"error": "Snapshot not found"})
        return b, c
    pair = store.get_latest_two()
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
    baseline_id: Optional[str] = Query(None),
    current_id: Optional[str] = Query(None),
    store: SnapshotStore = Depends(get_store),
):
    baseline, current = _resolve_pair(store, baseline_id, current_id)
    events = detect_drift(baseline, current)
    scored = score_all_events(events)
    counts = {"total": len(scored), "critical": 0, "high": 0, "medium": 0, "low": 0}
    for _, _, sev in scored:
        if sev in counts:
            counts[sev] += 1
    return counts


@router.get("/")
async def drift_analysis(
    baseline_id: Optional[str] = Query(None),
    current_id: Optional[str] = Query(None),
    store: SnapshotStore = Depends(get_store),
):
    baseline, current = _resolve_pair(store, baseline_id, current_id)
    return _run_drift(baseline, current)
