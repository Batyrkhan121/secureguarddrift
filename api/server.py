# api/server.py
# FastAPI-сервер SecureGuard Drift

import os
import csv
import time
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from core.rate_limiter import RateLimitMiddleware
from core.logging import setup_logging, RequestLoggingMiddleware
from pydantic import BaseModel
from auth.jwt_handler import jwt_handler

from graph.storage import SnapshotStore
from graph.builder import build_snapshot
from collector.ingress_parser import parse_log_file, get_time_windows, filter_by_time_window
from scripts.generate_mock_data import generate_rows, CSV_HEADER
from api.routes.graph_routes import router as graph_router, init_store as init_graph_store
from api.routes.drift_routes import router as drift_router, init_store as init_drift_store
from api.routes.report_routes import router as report_router, init_store as init_report_store
from api.routes.policy_routes import router as policy_router, init_store as init_policy_store
from api.routes.gitops_routes import router as gitops_router, init_stores as init_gitops_stores
from api.routes.integration_routes import router as integration_router
from api.routes.ml_routes import router as ml_router
from policy.storage import PolicyStore
from gitops.storage import GitOpsPRStore

# ---------------------------------------------------------------------------
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ---------------------------------------------------------------------------
# Bootstrap: fill DB with mock data if empty
# ---------------------------------------------------------------------------
def _bootstrap() -> None:
    if store.list_snapshots(tenant_id="default"):
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
        store.save_snapshot(snap, tenant_id="default")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    app.state.start_time = time.time()
    _bootstrap()
    yield


app = FastAPI(title="SecureGuardDrift API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Static files
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")

store = SnapshotStore(os.path.join(DATA_DIR, "snapshots.db"))
policy_store = PolicyStore(os.path.join(DATA_DIR, "policies.db"))
pr_store = GitOpsPRStore(os.path.join(DATA_DIR, "gitops_prs.db"))
init_graph_store(store)
init_drift_store(store)
init_report_store(store)
init_policy_store(policy_store)
init_gitops_stores(policy_store, pr_store)
app.include_router(graph_router)
app.include_router(drift_router)
app.include_router(report_router)
app.include_router(policy_router)
app.include_router(gitops_router)
app.include_router(integration_router)
app.include_router(ml_router)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))


@app.get("/api/health")
async def health():
    now = time.time()
    uptime = now - getattr(app.state, "start_time", now)
    snapshots = store.list_snapshots(tenant_id=None)
    snap_count = len(snapshots)

    # DB check
    try:
        t0 = time.time()
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("SELECT 1")
        db_status = {"status": "ok", "latency_ms": round((time.time() - t0) * 1000, 1)}
    except Exception:
        db_status = {"status": "error", "latency_ms": -1}

    # last snapshot age
    last_age = None
    if snapshots:
        last_ts = snapshots[-1].get("timestamp_end")
        if last_ts:
            last_age = int(now - datetime.fromisoformat(last_ts).replace(tzinfo=timezone.utc).timestamp())

    # DB size
    db_size = None
    try:
        db_size = os.path.getsize(store.db_path)
    except OSError:
        pass

    # system info (psutil optional)
    system = None
    try:
        import psutil
        proc = psutil.Process()
        system = {"memory_mb": round(proc.memory_info().rss / 1024 / 1024, 1), "cpu_percent": proc.cpu_percent()}
    except (ImportError, Exception):
        pass

    # overall status
    comp_statuses = [db_status["status"]]
    if db_status["status"] == "error":
        overall = "error"
    elif "degraded" in comp_statuses:
        overall = "degraded"
    else:
        overall = "ok"

    return {
        "status": overall,
        "version": app.version,
        "uptime_seconds": round(uptime, 1),
        "snapshots_count": snap_count,
        "last_snapshot_age_seconds": last_age,
        "db_size_bytes": db_size,
        "components": {
            "database": db_status,
            "collector": {"status": "ok", "last_run": None},
            "scheduler": {"status": "ok", "next_run": None},
        },
        "system": system,
    }


@app.get("/api/snapshots")
async def list_snapshots():
    return store.list_snapshots(tenant_id=None)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
DEMO_USERS = [
    {"email": "admin@demo.com", "password": "admin123", "role": "admin", "tenant_id": "demo"},
    {"email": "viewer@demo.com", "password": "viewer123", "role": "viewer", "tenant_id": "demo"},
]


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
async def login(body: LoginRequest):
    user = next((u for u in DEMO_USERS if u["email"] == body.email and u["password"] == body.password), None)
    if not user:
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
    token = jwt_handler.create_token(user_id=user["email"], email=user["email"], role=user["role"], tenant_id=user["tenant_id"])
    return {"token": token, "user": {"email": user["email"], "role": user["role"]}}




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
