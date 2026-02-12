# worker/tasks/notify.py
# Background task: route notifications to Slack/Jira/SIEM

import logging

from worker.app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=15)
def send_notifications_task(self, tenant_id: str, event_ids: list[str]):
    """Route notifications to configured integrations (Slack, Jira, SIEM).

    Args:
        tenant_id: Tenant identifier.
        event_ids: List of drift event identifiers to notify about.

    Returns:
        dict with notification results.
    """
    logger.info(
        "Sending notifications for tenant=%s, %d events",
        tenant_id, len(event_ids),
    )
    try:
        from integrations.config import IntegrationsSettings
        from integrations.router import NotificationRouter

        settings = IntegrationsSettings()
        router = NotificationRouter(settings)

        results = {"sent": [], "failed": [], "total": len(event_ids)}

        for event_id in event_ids:
            try:
                # Create minimal card for notification
                from drift.explainer import ExplainCard
                parts = event_id.split(":", 3)
                event_type = parts[1] if len(parts) > 1 else "unknown"
                risk_scores = {"new_edge": 60, "removed_edge": 40, "error_spike": 80,
                               "latency_spike": 50, "traffic_spike": 55, "blast_radius_increase": 75}
                card = ExplainCard(
                    event_type=event_type,
                    title=f"Drift: {event_id}",
                    what_changed=f"Drift event detected: {event_id}",
                    why_risk=["Automatic detection"],
                    affected=[parts[2] if len(parts) > 2 else "unknown"],
                    recommendation="Review the drift event in the dashboard",
                    risk_score=risk_scores.get(event_type, 50),
                    severity="high",
                    source=parts[2] if len(parts) > 2 else "unknown",
                    destination=parts[3] if len(parts) > 3 else "unknown",
                    rules_triggered=[],
                )
                result = router.route_event(card)
                if result.get("sent"):
                    results["sent"].append(event_id)
                else:
                    results["failed"].append(event_id)
            except Exception as e:
                logger.warning("Failed to notify for %s: %s", event_id, e)
                results["failed"].append(event_id)

        logger.info(
            "Notifications complete: %d sent, %d failed",
            len(results["sent"]), len(results["failed"]),
        )
        return results
    except Exception as exc:
        logger.error("Notification task failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=15 * (2 ** self.request.retries))
