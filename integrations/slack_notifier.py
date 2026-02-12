# integrations/slack_notifier.py
# Отправка drift-событий в Slack через Incoming Webhook

import time
import requests
from drift.explainer import ExplainCard


class SlackNotifier:
    """Отправка уведомлений в Slack."""

    def __init__(self, webhook_url: str, min_severity: str = "high", rate_limit_seconds: int = 60):
        self.webhook_url = webhook_url
        self.min_severity = min_severity
        self.rate_limit_seconds = rate_limit_seconds
        self._last_sent = {}  # event_type -> timestamp

    def should_send(self, event_type: str, severity: str) -> bool:
        """Проверяет rate limit и severity filter."""
        # Check severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        min_level = severity_order.get(self.min_severity, 1)
        event_level = severity_order.get(severity, 3)

        if event_level > min_level:
            return False

        # Check rate limit
        now = time.time()
        last_sent = self._last_sent.get(event_type, 0)

        if now - last_sent < self.rate_limit_seconds:
            return False

        return True

    def format_block_kit(self, card: ExplainCard) -> dict:
        """Форматирует сообщение в Slack Block Kit."""
        # Severity colors
        colors = {
            "critical": "#ff0000",
            "high": "#ff8800",
            "medium": "#ffcc00",
            "low": "#00aa00",
        }

        # Severity emoji
        emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }

        severity_badge = f"{emoji.get(card.severity, '⚪')} *{card.severity.upper()}*"
        risk_badge = f"Risk Score: *{card.risk_score}*"

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": card.title, "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": severity_badge},
                    {"type": "mrkdwn", "text": risk_badge},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*What changed:*\n{card.what_changed}"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Why risk:*\n" + "\n".join(f"• {r}" for r in card.why_risk),
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Affected:*\n{', '.join(card.affected)}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Recommendation:*\n{card.recommendation}"},
            },
        ]

        return {
            "attachments": [
                {
                    "color": colors.get(card.severity, "#808080"),
                    "blocks": blocks,
                }
            ]
        }

    def send_notification(self, card: ExplainCard) -> bool:
        """Отправляет уведомление в Slack.

        Returns:
            True если отправлено успешно
        """
        if not self.webhook_url:
            return False

        if not self.should_send(card.event_type, card.severity):
            return False

        try:
            payload = self.format_block_kit(card)
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()

            # Update rate limit tracker
            self._last_sent[card.event_type] = time.time()
            return True

        except Exception as e:
            print(f"Failed to send Slack notification: {e}")
            return False


if __name__ == "__main__":
    # Example usage
    from drift.explainer import ExplainCard

    card = ExplainCard(
        event_type="new_edge",
        title="Test Event",
        what_changed="Test change",
        why_risk=["Test risk"],
        affected=["svc1", "svc2"],
        recommendation="Test recommendation",
        risk_score=85,
        severity="critical",
        source="svc1",
        destination="svc2",
        rules_triggered=["test_rule"],
    )

    notifier = SlackNotifier("https://hooks.slack.com/test")
    print(f"Block Kit: {notifier.format_block_kit(card)}")
