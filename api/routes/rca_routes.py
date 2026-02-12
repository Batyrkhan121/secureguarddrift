# api/routes/rca_routes.py
# Root Cause Analysis API routes

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from graph.storage import SnapshotStore
from ml.rca.causal import CausalAnalyzer
from ml.rca.blast_radius import BlastRadiusPredictor
from ml.rca.predictor import DriftPredictor
from api.routes import get_tenant_id

router = APIRouter(prefix="/api/rca", tags=["rca"])

_store: SnapshotStore | None = None


def init_store(s: SnapshotStore) -> None:
    global _store
    _store = s


def get_store() -> SnapshotStore:
    assert _store is not None, "Store not initialized"
    return _store


class PredictDriftRequest(BaseModel):
    add_services: list[str] = []
    remove_services: list[str] = []
    add_edges: list[dict] = []
    modify_configs: list[dict] = []


@router.get("/root-cause")
async def root_cause(request: Request, snapshot_id: str):
    tenant_id = get_tenant_id(request) or "default"
    store = get_store()
    snap = store.load_snapshot(snapshot_id, tenant_id=tenant_id)
    if snap is None:
        raise HTTPException(404, "Snapshot not found")

    snapshot_dict = _snap_to_dict(snap)
    error_events = [
        {"source": e.source, "destination": e.destination,
         "event_type": "error_spike", "severity": "high"}
        for e in snap.edges if e.error_rate() > 0.05
    ]

    analyzer = CausalAnalyzer()
    results = analyzer.find_root_cause(snapshot_dict, error_events)
    return {"snapshot_id": snapshot_id, "root_causes": results}


@router.get("/blast-radius")
async def blast_radius(request: Request, service: str, snapshot_id: str):
    tenant_id = get_tenant_id(request) or "default"
    store = get_store()
    snap = store.load_snapshot(snapshot_id, tenant_id=tenant_id)
    if snap is None:
        raise HTTPException(404, "Snapshot not found")

    snapshot_dict = _snap_to_dict(snap)
    predictor = BlastRadiusPredictor()
    result = predictor.predict(snapshot_dict, service)
    return result


@router.post("/predict-drift")
async def predict_drift(request: Request, body: PredictDriftRequest):
    tenant_id = get_tenant_id(request) or "default"
    store = get_store()
    snaps = store.list_snapshots(tenant_id=tenant_id)
    if not snaps:
        raise HTTPException(404, "No snapshots available")

    latest = store.load_snapshot(snaps[-1]["snapshot_id"], tenant_id=tenant_id)
    if latest is None:
        raise HTTPException(404, "Latest snapshot not found")

    snapshot_dict = _snap_to_dict(latest)
    predictor = DriftPredictor()
    predictions = predictor.predict_from_diff(
        snapshot_dict,
        {
            "add_services": body.add_services,
            "remove_services": body.remove_services,
            "add_edges": body.add_edges,
            "modify_configs": body.modify_configs,
        },
    )
    return {"predictions": predictions}


def _snap_to_dict(snap) -> dict:
    return {
        "nodes": [{"name": n.name, "namespace": n.namespace,
                    "node_type": n.node_type} for n in snap.nodes],
        "edges": [{"source": e.source, "destination": e.destination,
                    "request_count": e.request_count, "error_count": e.error_count,
                    "error_rate": round(e.error_rate(), 4),
                    "avg_latency_ms": e.avg_latency_ms,
                    "p99_latency_ms": e.p99_latency_ms} for e in snap.edges],
    }
