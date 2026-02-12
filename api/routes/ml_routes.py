# api/routes/ml_routes.py
"""API endpoints для ML функциональности."""

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from graph.storage import SnapshotStore
from ml.baseline import build_baseline
from ml.feedback import FeedbackRecord, FeedbackStore
from ml.whitelist import WhitelistEntry, WhitelistStore
from api.routes import get_tenant_id

router = APIRouter(prefix="/api", tags=["ml"])

# Stores
feedback_store = FeedbackStore()
whitelist_store = WhitelistStore()
snapshot_store = SnapshotStore()


# Request/Response models
class FeedbackRequest(BaseModel):
    event_id: str
    source: str
    destination: str
    event_type: str
    verdict: Literal["true_positive", "false_positive", "expected"]
    comment: Optional[str] = None
    user: Optional[str] = None


class WhitelistRequest(BaseModel):
    source: str
    destination: str
    reason: str
    created_by: Optional[str] = None


class SuppressRuleRequest(BaseModel):
    event_type: str
    service_pattern: str
    reason: str
    expires_hours: int = 24
    created_by: Optional[str] = None


# Endpoints
@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest, request: Request):
    """Сохраняет user feedback на drift событие."""
    feedback = FeedbackRecord(
        feedback_id=None,
        event_id=req.event_id,
        edge_key=(req.source, req.destination),
        event_type=req.event_type,
        verdict=req.verdict,
        comment=req.comment,
        user=req.user,
        created_at=datetime.now(timezone.utc),
    )

    feedback_id = feedback_store.save_feedback(feedback)

    # Если verdict="expected", автоматически добавляем в whitelist
    if req.verdict == "expected":
        entry = WhitelistEntry(
            entry_id=None,
            source=req.source,
            destination=req.destination,
            reason=f"Auto-whitelisted from feedback: {req.comment or 'expected behavior'}",
            created_at=datetime.now(timezone.utc),
            created_by=req.user,
        )
        whitelist_store.add_to_whitelist(entry)

    return {"feedback_id": feedback_id, "status": "saved", "auto_whitelisted": req.verdict == "expected"}


@router.get("/whitelist")
async def get_whitelist(request: Request):
    """Возвращает список всех whitelisted edges."""
    entries = whitelist_store.list_whitelist()
    return {
        "count": len(entries),
        "entries": [
            {
                "entry_id": e.entry_id,
                "source": e.source,
                "destination": e.destination,
                "reason": e.reason,
                "created_by": e.created_by,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
    }


@router.post("/whitelist")
async def add_to_whitelist(req: WhitelistRequest, request: Request):
    """Добавляет edge в whitelist."""
    entry = WhitelistEntry(
        entry_id=None,
        source=req.source,
        destination=req.destination,
        reason=req.reason,
        created_at=datetime.now(timezone.utc),
        created_by=req.created_by,
    )

    entry_id = whitelist_store.add_to_whitelist(entry)
    return {"entry_id": entry_id, "status": "added"}


@router.delete("/whitelist/{source}/{destination}")
async def remove_from_whitelist(source: str, destination: str, request: Request):
    """Удаляет edge из whitelist."""
    deleted = whitelist_store.remove_from_whitelist((source, destination))

    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found in whitelist")

    return {"status": "removed", "edge": f"{source} -> {destination}"}


@router.get("/baseline/{source}/{destination}")
async def get_baseline(source: str, destination: str, request: Request):
    """Возвращает baseline профиль для edge."""
    tenant_id = get_tenant_id(request)
    # Загружаем последние снапшоты
    snapshots = snapshot_store.list_snapshots(tenant_id=tenant_id)

    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots available")

    # Строим baseline
    edge_key = (source, destination)
    baseline = build_baseline(snapshots, edge_key)

    if baseline is None:
        raise HTTPException(status_code=404, detail="Insufficient data for baseline")

    return {
        "edge_key": edge_key,
        "request_count": {"mean": baseline.request_count_mean, "std": baseline.request_count_std},
        "error_rate": {"mean": baseline.error_rate_mean, "std": baseline.error_rate_std},
        "p99_latency": {"mean": baseline.p99_latency_mean, "std": baseline.p99_latency_std},
        "sample_count": baseline.sample_count,
        "last_updated": baseline.last_updated.isoformat() if baseline.last_updated else None,
    }
