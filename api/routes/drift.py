# api/routes/drift.py
# GET drift-события

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from graph.storage import SQLiteStorage
from drift.detector import DriftDetector
from drift.scorer import RiskScorer
from drift.explainer import DriftExplainer

router = APIRouter()
storage = SQLiteStorage()
detector = DriftDetector()
scorer = RiskScorer()
explainer = DriftExplainer()


@router.get("/latest")
async def get_latest_drift():
    """Получить последний drift-анализ (сравнение двух последних снапшотов)."""
    latest = storage.get_latest()
    if not latest:
        raise HTTPException(status_code=404, detail="No snapshots available")

    previous = storage.get_previous(latest.id)
    if not previous:
        return {"message": "Only one snapshot available, no drift to detect"}

    events = detector.compare(previous, latest)
    risk = scorer.score_events(events)
    explanations = explainer.explain_all(events)
    summary = explainer.generate_summary(events)

    return {
        "snapshot_before": previous.id,
        "snapshot_after": latest.id,
        "risk": risk,
        "explanations": explanations,
        "summary": summary,
    }


@router.get("/compare")
async def compare_snapshots(
    before: str = Query(..., description="ID снапшота 'до'"),
    after: str = Query(..., description="ID снапшота 'после'"),
):
    """Сравнить два конкретных снапшота."""
    snap_before = storage.load(before)
    snap_after = storage.load(after)

    if not snap_before:
        raise HTTPException(status_code=404, detail=f"Snapshot {before} not found")
    if not snap_after:
        raise HTTPException(status_code=404, detail=f"Snapshot {after} not found")

    events = detector.compare(snap_before, snap_after)
    risk = scorer.score_events(events)
    explanations = explainer.explain_all(events)
    summary = explainer.generate_summary(events)

    return {
        "snapshot_before": before,
        "snapshot_after": after,
        "risk": risk,
        "explanations": explanations,
        "summary": summary,
    }


@router.get("/events")
async def list_drift_events(
    limit: int = Query(default=20, le=100),
):
    """Получить последние drift-события."""
    snapshots = storage.list_snapshots(limit=limit + 1)
    all_events = []

    for i in range(len(snapshots) - 1):
        after_snap = storage.load(snapshots[i]["id"])
        before_snap = storage.load(snapshots[i + 1]["id"])
        if after_snap and before_snap:
            events = detector.compare(before_snap, after_snap)
            for event in events:
                all_events.append(event.to_dict())

    return all_events[:limit]
