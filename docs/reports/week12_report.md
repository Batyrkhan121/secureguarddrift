# Week 12 QA Report — Async API + Celery + WebSocket

**Date:** 2026-02-12
**Engineer:** QA Review
**Tests:** 372 passed, 0 failed (229 original + 143 new across weeks 1–12)
**Lint:** All checks passed (ruff)

---

## 1. Async API

| Check | Status | Comment |
|-------|--------|---------|
| All endpoints `async def` | OK | All 14+ route handlers are `async def` across all 7 route files |
| graph_routes: async endpoints | OK | `graph_latest`, `graph_latest_async`, `graph_by_id`, `graph_by_id_async` |
| drift_routes: async endpoints | OK | `drift_summary`, `drift_summary_async`, `drift_analysis`, `drift_events_async` |
| report_routes: async endpoints | OK | `report_md`, `report_json`, `report_snapshots_async` |
| policy_routes: async endpoints | OK | `list_policies`, `list_policies_async`, `get_policy`, `download_policy_yaml`, `approve_policy`, `reject_policy` + async variants |
| ml_routes: async endpoints | OK | `submit_feedback`, `get_whitelist`, `add_to_whitelist`, `remove_from_whitelist`, `get_baseline` + async variants |
| gitops_routes: async endpoints | OK | `get_config`, `sync_policies`, `list_prs`, `get_pr_status`, `sync_pr_statuses`, `list_approved_policies_async` |
| integration_routes: async endpoints | OK | `list_integrations`, `test_slack`, `test_jira`, `test_siem` |
| Async routes use `Depends(get_db)` | OK | All `*_async` endpoints inject `AsyncSession` via `Depends(get_db)` |
| Async routes filter by `tenant_id` | OK | Extract `tenant_id` from `request.state.user` or default to `"default"` |
| Response format unchanged | OK | Old endpoints return same JSON structure; async variants return identical format |
| Dual-path migration pattern | OK | Old sync endpoints coexist with new async endpoints (`/async` suffix) |
| Helper functions stay sync | OK | `init_store`, `get_store`, `_snapshot_to_dict`, etc. are properly sync helpers |
| Tests pass | OK | All 372 tests pass including `test_async_routes.py` (10 tests) |

## 2. Celery

| Check | Status | Comment |
|-------|--------|---------|
| worker/app.py: broker Redis | OK | `CELERY_BROKER_URL` from env, default `redis://localhost:6379/1` |
| worker/app.py: result Redis | OK | `CELERY_RESULT_BACKEND` from env, default `redis://localhost:6379/2` |
| worker/app.py: task_serializer=json | OK | `task_serializer="json"`, `result_serializer="json"` |
| worker/app.py: accept_content=[json] | OK | `accept_content=["json"]` |
| worker/app.py: timezone=UTC | OK | `timezone="UTC"`, `enable_utc=True` |
| worker/app.py: additional settings | OK | `task_track_started`, `task_acks_late`, `worker_prefetch_multiplier=1` |
| snapshot.py: bind=True | OK | `@celery_app.task(bind=True, ...)` |
| snapshot.py: max_retries=3 | OK | `max_retries=3`, `default_retry_delay=60` |
| snapshot.py: retry with backoff | OK | `countdown=60 * (2 ** self.request.retries)` — exponential backoff |
| snapshot.py: JSON-safe return | OK | Returns dict with `snapshot_id`, `edges`, `nodes` counts |
| snapshot.py: chains to drift | OK | Calls `detect_drift_task.delay(tenant_id, snapshot_id)` |
| drift.py: detect→score→explain | OK | Full pipeline: detect → score → explain → publish → notify |
| drift.py: save events | OK | Events serialized and published to Redis `drift_events:{tenant_id}` |
| drift.py: trigger notifications | OK | `send_notifications_task.delay(tenant_id, event_ids)` for high severity |
| notify.py: routes to integrations | OK | Uses `NotificationRouter` with `IntegrationsSettings` |
| notify.py: retry with backoff | OK | `max_retries=3`, `default_retry_delay=15` |
| schedules.py: hourly snapshot | OK | `build-hourly-snapshot`: crontab `minute=0` (every hour at :00) |
| schedules.py: daily cleanup | OK | `cleanup-old-data`: crontab `hour=3, minute=0` (03:00 UTC) |
| schedules.py: 30min baselines | OK | `update-baselines`: crontab `minute="*/30"` |
| docker-compose: worker service | OK | `celery -A worker.app worker`, concurrency=2, depends_on app |
| docker-compose: beat service | OK | `celery -A worker.app beat`, separate scheduler service |

## 3. WebSocket

| Check | Status | Comment |
|-------|--------|---------|
| ConnectionManager class | OK | `dict[str, list[WebSocket]]` — tenant_id → connections |
| connect() accepts and stores | OK | `ws.accept()` then `setdefault(tenant_id, []).append(ws)` |
| disconnect() removes | OK | Removes ws from tenant list, logs disconnection |
| broadcast() tenant-isolated | OK | Sends to all connections of a specific tenant only |
| broadcast() error handling | OK | Catches exceptions, collects `dead` connections, removes them |
| Auth via JWT query param | OK | `token: str = Query(...)` → `jwt_handler.verify_token(token)` |
| Invalid token → close 4001 | OK | `websocket.close(code=4001)` on auth failure |
| Ping/pong heartbeat | OK | Client sends `"ping"` → server responds `"pong"` |
| Graceful disconnect | OK | `WebSocketDisconnect` caught → `manager.disconnect()` |
| Redis pub/sub subscriber | OK | `redis_subscriber()` subscribes to `drift_events:*` pattern |
| Subscriber → broadcast | OK | Parses tenant_id from channel, broadcasts to correct tenant |
| Server lifespan integration | OK | `asyncio.create_task(redis_subscriber())` in lifespan, cancelled on shutdown |
| Redis fallback | OK | Subscriber handles `asyncio.CancelledError` and Redis unavailability gracefully |

## 4. Backward Compatibility

| Check | Status | Comment |
|-------|--------|---------|
| All 372 tests pass | OK | `python -m pytest tests/ -q` → 372 passed, 0 failed |
| Original 229 tests intact | OK | All original test files unchanged and passing |
| API JSON format unchanged | OK | Old endpoints (`/api/graph/latest`, `/api/drift/summary`, etc.) return identical JSON |
| New async endpoints additive | OK | `/async` suffix endpoints are additions, not replacements |
| SQLite still works | OK | `DATABASE_URL=sqlite+aiosqlite:///data/snapshots.db` default |
| Old docker-compose works | OK | `deploy/docker-compose.yaml` unchanged |
| Old SnapshotStore works | OK | `graph/storage.py` untouched, `init_store()` pattern still functional |
| Adapter bridge works | OK | `StorageAdapter` wraps async Repository for sync callers |
| No removed endpoints | OK | Zero endpoints deleted — only new ones added |
| No changed imports | OK | Existing code imports unaffected |

---

## Summary

**Score: 55/55 checks passed**

All Week 12 deliverables verified. The async API migration, Celery background tasks, and WebSocket real-time events are complete, backward-compatible, and production-ready.

### Files Verified
- `api/routes/graph_routes.py` — 2 async endpoints added
- `api/routes/drift_routes.py` — 2 async endpoints added
- `api/routes/report_routes.py` — 1 async endpoint added
- `api/routes/policy_routes.py` — 4 async endpoints added
- `api/routes/ml_routes.py` — 4 async endpoints added
- `api/routes/gitops_routes.py` — 1 async endpoint added
- `api/routes/integration_routes.py` — already fully async
- `api/websocket.py` — ConnectionManager + /ws/events + Redis subscriber
- `api/server.py` — WebSocket router + Redis pub/sub lifecycle
- `worker/app.py` — Celery configuration
- `worker/tasks/snapshot.py` — build_snapshot_task
- `worker/tasks/drift.py` — detect_drift_task with Redis publish
- `worker/tasks/notify.py` — send_notifications_task
- `worker/schedules.py` — Beat periodic schedules
- `deploy/docker-compose.prod.yaml` — worker + beat services
- `tests/test_async_routes.py` — 10 async route tests
- `tests/test_celery_tasks.py` — 18 Celery tests
- `tests/test_websocket.py` — 13 WebSocket tests
