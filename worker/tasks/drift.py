# worker/tasks/drift.py
# Background task: detect drift → score → explain → save → notify

import logging

from worker.app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def detect_drift_task(self, tenant_id: str, snapshot_id: str):
    """Detect drift between latest two snapshots, score, explain, and notify.

    Args:
        tenant_id: Tenant identifier.
        snapshot_id: ID of the newly created snapshot.

    Returns:
        dict with event count and event IDs.
    """
    from graph.storage import SnapshotStore
    from drift.detector import detect_drift
    from drift.scorer import score_all_events
    from drift.explainer import explain_event

    logger.info("Detecting drift for tenant=%s snapshot=%s", tenant_id, snapshot_id)
    try:
        store = SnapshotStore()
        pair = store.get_latest_two(tenant_id=tenant_id)
        if pair is None:
            logger.info("Less than 2 snapshots for tenant=%s, skipping drift", tenant_id)
            return {"events": 0, "event_ids": [], "status": "skipped"}

        baseline, current = pair

        # Detect drift events
        events = detect_drift(baseline, current)
        if not events:
            logger.info("No drift detected for tenant=%s", tenant_id)
            return {"events": 0, "event_ids": [], "status": "clean"}

        # Score all events
        scored = score_all_events(events)

        # Explain each event and collect cards
        cards = []
        for event, score, severity in scored:
            card = explain_event(event, score, severity)
            cards.append(card)

        event_ids = [f"{tenant_id}:{event.event_type}:{event.source}:{event.destination}"
                     for event, _, _ in scored]

        logger.info("Drift detected: %d events for tenant=%s", len(events), tenant_id)

        # Trigger notifications for high-severity events
        high_severity_ids = [
            eid for eid, (_, _, sev) in zip(event_ids, scored)
            if sev in ("critical", "high")
        ]
        if high_severity_ids:
            from worker.tasks.notify import send_notifications_task
            send_notifications_task.delay(tenant_id, high_severity_ids)

        return {
            "events": len(events),
            "event_ids": event_ids,
            "status": "detected",
        }
    except Exception as exc:
        logger.error("Drift detection failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
