# api/routes/report_routes.py
# Роутер для генерации отчётов

import os
import tempfile
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from graph.models import Snapshot
from graph.storage import SnapshotStore
from drift.detector import detect_drift
from drift.scorer import score_all_events
from drift.explainer import explain_all
from drift.report import generate_report

router = APIRouter(prefix="/api/report", tags=["report"])

_store: SnapshotStore | None = None


def init_store(s: SnapshotStore) -> None:
    global _store
    _store = s


def get_store() -> SnapshotStore:
    assert _store is not None, "Store not initialized"
    return _store


def _pair(store: SnapshotStore, bid: Optional[str], cid: Optional[str]):
    if bid and cid:
        b, c = store.load_snapshot(bid), store.load_snapshot(cid)
        if b is None or c is None:
            raise HTTPException(404, detail={"error": "Snapshot not found"})
        return b, c
    pair = store.get_latest_two()
    if pair is None:
        raise HTTPException(404, detail={"error": "Need at least 2 snapshots"})
    return pair


def _build_cards(baseline: Snapshot, current: Snapshot):
    events = detect_drift(baseline, current)
    scored = score_all_events(events)
    return scored, explain_all(scored), baseline, current


@router.get("/md")
async def report_md(
    baseline_id: Optional[str] = Query(None),
    current_id: Optional[str] = Query(None),
    store: SnapshotStore = Depends(get_store),
):
    b, c = _pair(store, baseline_id, current_id)
    scored, cards, _, _ = _build_cards(b, c)
    fd, tmp = tempfile.mkstemp(suffix=".md"); os.close(fd)
    content = generate_report(b, c, cards, output_path=tmp)
    return Response(content=content, media_type="text/markdown",
                    headers={"Content-Disposition": 'attachment; filename="drift_report.md"'})


@router.get("/json")
async def report_json(
    baseline_id: Optional[str] = Query(None),
    current_id: Optional[str] = Query(None),
    store: SnapshotStore = Depends(get_store),
):
    b, c = _pair(store, baseline_id, current_id)
    scored, cards, _, _ = _build_cards(b, c)
    sev = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for _, _, s in scored:
        sev[s] = sev.get(s, 0) + 1
    return {
        "baseline_id": b.snapshot_id, "current_id": c.snapshot_id,
        "summary": {"total": len(cards), **sev},
        "cards": [{"event_type": cd.event_type, "title": cd.title,
                    "what_changed": cd.what_changed, "why_risk": cd.why_risk,
                    "affected": cd.affected, "recommendation": cd.recommendation,
                    "risk_score": cd.risk_score, "severity": cd.severity} for cd in cards],
    }
