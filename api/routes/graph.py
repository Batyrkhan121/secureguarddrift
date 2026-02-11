# api/routes/graph.py
# GET текущий граф

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from graph.storage import SQLiteStorage

router = APIRouter()
storage = SQLiteStorage()


@router.get("/current")
async def get_current_graph():
    """Получить текущий (последний) снапшот графа."""
    snapshot = storage.get_latest()
    if not snapshot:
        raise HTTPException(status_code=404, detail="No snapshots found")
    return snapshot.to_dict()


@router.get("/snapshots")
async def list_snapshots(limit: int = Query(default=50, le=200)):
    """Список доступных снапшотов."""
    return storage.list_snapshots(limit=limit)


@router.get("/snapshots/{snapshot_id}")
async def get_snapshot(snapshot_id: str):
    """Получить конкретный снапшот по ID."""
    snapshot = storage.load(snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} not found")
    return snapshot.to_dict()


@router.get("/diff")
async def get_graph_diff(
    before: str = Query(..., description="ID снапшота 'до'"),
    after: str = Query(..., description="ID снапшота 'после'"),
):
    """Получить разницу между двумя снапшотами."""
    snap_before = storage.load(before)
    snap_after = storage.load(after)

    if not snap_before:
        raise HTTPException(status_code=404, detail=f"Snapshot {before} not found")
    if not snap_after:
        raise HTTPException(status_code=404, detail=f"Snapshot {after} not found")

    before_nodes = {n.id for n in snap_before.nodes}
    after_nodes = {n.id for n in snap_after.nodes}
    before_edges = {(e.source, e.target) for e in snap_before.edges}
    after_edges = {(e.source, e.target) for e in snap_after.edges}

    return {
        "added_nodes": list(after_nodes - before_nodes),
        "removed_nodes": list(before_nodes - after_nodes),
        "added_edges": [{"source": s, "target": t} for s, t in after_edges - before_edges],
        "removed_edges": [{"source": s, "target": t} for s, t in before_edges - after_edges],
    }
