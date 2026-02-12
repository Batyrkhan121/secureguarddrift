# api/routes/graph_routes.py
# Роутер для эндпоинтов графа

from fastapi import APIRouter, Depends, HTTPException, Request
from graph.models import Snapshot
from graph.storage import SnapshotStore
from api.routes import get_tenant_id

router = APIRouter(prefix="/api/graph", tags=["graph"])

_store: SnapshotStore | None = None


def init_store(s: SnapshotStore) -> None:
    """Вызывается из server.py для инициализации store."""
    global _store
    _store = s


def get_store() -> SnapshotStore:
    """FastAPI dependency — возвращает SnapshotStore."""
    assert _store is not None, "Store not initialized"
    return _store


def _snapshot_to_dict(snap: Snapshot) -> dict:
    return {
        "snapshot_id": snap.snapshot_id,
        "nodes": [{"name": n.name, "namespace": n.namespace,
                    "node_type": n.node_type} for n in snap.nodes],
        "edges": [{"source": e.source, "destination": e.destination,
                    "request_count": e.request_count, "error_count": e.error_count,
                    "error_rate": round(e.error_rate(), 4),
                    "avg_latency_ms": e.avg_latency_ms,
                    "p99_latency_ms": e.p99_latency_ms} for e in snap.edges],
    }


def _snap_or_404(sid: str, store: SnapshotStore, tenant_id: str) -> Snapshot:
    snap = store.load_snapshot(sid, tenant_id=tenant_id)
    if snap is None:
        raise HTTPException(status_code=404, detail={"error": "Snapshot not found"})
    return snap


@router.get("/latest")
async def graph_latest(request: Request, store: SnapshotStore = Depends(get_store)):
    tenant_id = get_tenant_id(request)
    pair = store.get_latest_two(tenant_id=tenant_id)
    if pair is None:
        snaps = store.list_snapshots(tenant_id=tenant_id)
        if not snaps:
            raise HTTPException(status_code=404, detail={"error": "Snapshot not found"})
        snap = store.load_snapshot(snaps[-1]["snapshot_id"], tenant_id=tenant_id)
    else:
        snap = pair[1]
    return _snapshot_to_dict(snap)


@router.get("/{snapshot_id}")
async def graph_by_id(snapshot_id: str, request: Request, store: SnapshotStore = Depends(get_store)):
    tenant_id = get_tenant_id(request)
    return _snapshot_to_dict(_snap_or_404(snapshot_id, store, tenant_id))
