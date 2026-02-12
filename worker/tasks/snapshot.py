# worker/tasks/snapshot.py
# Background task: parse logs → build graph → save snapshot → trigger drift

import logging
from datetime import datetime, timezone

from worker.app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def build_snapshot_task(self, tenant_id: str, log_path: str):
    """Parse logs → build graph → save snapshot → trigger drift detection.

    Args:
        tenant_id: Tenant identifier.
        log_path: Path to log file for parsing.

    Returns:
        dict with snapshot_id and edge count.
    """
    from collector.auto_detect import parse_log_file
    from graph.builder import build_snapshot
    from graph.storage import SnapshotStore

    logger.info("Building snapshot for tenant=%s from %s", tenant_id, log_path)
    try:
        records = parse_log_file(log_path)
        if not records:
            logger.warning("No records parsed from %s", log_path)
            return {"snapshot_id": None, "edges": 0, "status": "empty"}

        timestamps = [r["timestamp"] for r in records if "timestamp" in r]
        start = min(timestamps) if timestamps else datetime.now(timezone.utc)
        end = max(timestamps) if timestamps else datetime.now(timezone.utc)
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        snapshot = build_snapshot(records, start, end)

        store = SnapshotStore()
        store.save_snapshot(snapshot, tenant_id=tenant_id)

        logger.info(
            "Snapshot %s saved: %d edges, %d nodes",
            snapshot.snapshot_id, len(snapshot.edges), len(snapshot.nodes),
        )

        # Trigger drift detection as next step in the pipeline
        from worker.tasks.drift import detect_drift_task
        detect_drift_task.delay(tenant_id, snapshot.snapshot_id)

        return {
            "snapshot_id": snapshot.snapshot_id,
            "edges": len(snapshot.edges),
            "nodes": len(snapshot.nodes),
        }
    except Exception as exc:
        logger.error("Snapshot build failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
