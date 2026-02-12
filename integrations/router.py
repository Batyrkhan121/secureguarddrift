# integrations/router.py
# Маршрутизация уведомлений по правилам

from drift.explainer import ExplainCard
from integrations.config import IntegrationsSettings
from integrations.slack_notifier import SlackNotifier
from integrations.jira_client import JiraClient
from integrations.siem_exporter import SIEMExporter


class NotificationRouter:
    """Маршрутизация drift-событий в интеграции."""

    def __init__(self, settings: IntegrationsSettings):
        self.settings = settings

        # Initialize integrations
        self.slack = None
        if settings.slack_enabled and settings.slack_webhook_url:
            self.slack = SlackNotifier(
                webhook_url=settings.slack_webhook_url,
                min_severity=settings.slack_min_severity,
                rate_limit_seconds=settings.slack_rate_limit_seconds,
            )

        self.jira = None
        if settings.jira_enabled and settings.jira_url:
            self.jira = JiraClient(
                url=settings.jira_url,
                email=settings.jira_email,
                api_token=settings.jira_api_token,
                project_key=settings.jira_project_key,
                issue_type=settings.jira_issue_type,
            )

        self.siem = None
        if settings.siem_enabled:
            self.siem = SIEMExporter(
                transport=settings.siem_transport,
                syslog_host=settings.siem_syslog_host,
                syslog_port=settings.siem_syslog_port,
                syslog_protocol=settings.siem_syslog_protocol,
                webhook_url=settings.siem_webhook_url,
            )

    def get_targets_for_severity(self, severity: str) -> list[str]:
        """Возвращает список targets для severity level."""
        target_map = {
            "critical": self.settings.router_critical_targets,
            "high": self.settings.router_high_targets,
            "medium": self.settings.router_medium_targets,
            "low": self.settings.router_low_targets,
        }

        targets_str = target_map.get(severity, "")
        if not targets_str:
            return []

        return [t.strip() for t in targets_str.split(",") if t.strip()]

    def route_event(self, card: ExplainCard) -> dict:
        """Маршрутизирует событие в нужные интеграции.

        Returns:
            dict с результатами отправки
        """
        targets = self.get_targets_for_severity(card.severity)
        results = {"targets": targets, "sent": []}

        for target in targets:
            if target == "slack" and self.slack:
                success = self.slack.send_notification(card)
                if success:
                    results["sent"].append("slack")

            elif target == "jira" and self.jira:
                result = self.jira.create_issue(card)
                if result:
                    results["sent"].append("jira")
                    results["jira_result"] = result

            elif target == "siem" and self.siem:
                success = self.siem.export_event(card)
                if success:
                    results["sent"].append("siem")

        return results


if __name__ == "__main__":
    from drift.explainer import ExplainCard
    from integrations.config import settings

    card = ExplainCard(
        event_type="new_edge",
        title="Test Event",
        what_changed="Test",
        why_risk=["Risk"],
        affected=["svc1"],
        recommendation="Fix",
        risk_score=85,
        severity="critical",
        source="svc1",
        destination="svc2",
        rules_triggered=[],
    )

    router = NotificationRouter(settings)
    print(f"Targets: {router.get_targets_for_severity('critical')}")
