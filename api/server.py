# api/server.py
# FastAPI-сервер SecureGuard Drift

import csv
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from graph.storage import SnapshotStore
from graph.builder import build_snapshot
from collector.ingress_parser import parse_log_file, get_time_windows, filter_by_time_window
from scripts.generate_mock_data import generate_rows, CSV_HEADER
from api.routes.graph_routes import router as graph_router, init_store as init_graph_store
from api.routes.drift_routes import router as drift_router, init_store as init_drift_store
from api.routes.report_routes import router as report_router, init_store as init_report_store

# ---------------------------------------------------------------------------
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

app = FastAPI(title="SecureGuardDrift API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")

store = SnapshotStore(os.path.join(DATA_DIR, "snapshots.db"))
init_graph_store(store)
init_drift_store(store)
init_report_store(store)
app.include_router(graph_router)
app.include_router(drift_router)
app.include_router(report_router)


# ---------------------------------------------------------------------------
# Bootstrap: fill DB with mock data if empty
# ---------------------------------------------------------------------------
def _bootstrap() -> None:
    if store.list_snapshots():
        return
    csv_path = os.path.join(DATA_DIR, "mock_ingress.csv")
    if not os.path.exists(csv_path):
        os.makedirs(DATA_DIR, exist_ok=True)
        rows = generate_rows(datetime(2026, 2, 10, 10, 0, 0), 3)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_HEADER)
            w.writerows(rows)
    records = parse_log_file(csv_path)
    windows = get_time_windows(records, window_hours=1)
    for s, e in windows:
        snap = build_snapshot(filter_by_time_window(records, s, e), s, e)
        store.save_snapshot(snap)


@app.on_event("startup")
def on_startup():
    _bootstrap()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "snapshots_count": len(store.list_snapshots())}


@app.get("/api/snapshots")
async def list_snapshots():
    return store.list_snapshots()




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
