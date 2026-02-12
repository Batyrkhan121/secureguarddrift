# tests/test_week8_integrations.py
# Тесты для интеграций (Неделя 8)

import unittest
from unittest.mock import Mock, patch
from integrations.config import IntegrationsSettings
from integrations.slack_notifier import SlackNotifier
from integrations.jira_client import JiraClient
from integrations.siem_exporter import SIEMExporter
from integrations.router import NotificationRouter
from drift.explainer import ExplainCard


class TestSlackNotifier(unittest.TestCase):
    """Тесты Slack notifier."""

    def setUp(self):
        self.notifier = SlackNotifier("https://hooks.slack.com/test", min_severity="high")

    def test_should_send_severity_filter(self):
        """Severity filter работает."""
        self.assertTrue(self.notifier.should_send("test", "critical"))
        self.assertTrue(self.notifier.should_send("test", "high"))
        self.assertFalse(self.notifier.should_send("test", "medium"))
        self.assertFalse(self.notifier.should_send("test", "low"))

    def test_format_block_kit(self):
        """Block Kit форматируется корректно."""
        card = ExplainCard(
            event_type="new_edge",
            title="Test Event",
            what_changed="Test change",
            why_risk=["Risk 1", "Risk 2"],
            affected=["svc1", "svc2"],
            recommendation="Fix it",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
            rules_triggered=["rule1"],
        )

        block_kit = self.notifier.format_block_kit(card)

        # Check structure
        self.assertIn("attachments", block_kit)
        self.assertEqual(len(block_kit["attachments"]), 1)

        attachment = block_kit["attachments"][0]
        self.assertIn("blocks", attachment)
        self.assertIn("color", attachment)
        self.assertEqual(attachment["color"], "#ff0000")  # critical = red

        # Check blocks
        blocks = attachment["blocks"]
        self.assertTrue(any(b["type"] == "header" for b in blocks))

    @patch("integrations.slack_notifier.requests.post")
    def test_send_notification(self, mock_post):
        """Отправка notification работает."""
        mock_post.return_value.raise_for_status = Mock()

        card = ExplainCard(
            event_type="new_edge",
            title="Test",
            what_changed="Test",
            why_risk=["Test"],
            affected=["svc1"],
            recommendation="Test",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
            rules_triggered=[],
        )

        success = self.notifier.send_notification(card)

        self.assertTrue(success)
        mock_post.assert_called_once()


class TestJiraClient(unittest.TestCase):
    """Тесты Jira client."""

    def setUp(self):
        self.client = JiraClient(
            url="https://test.atlassian.net",
            email="test@test.com",
            api_token="token",
            project_key="TEST",
        )

    def test_format_description(self):
        """Description форматируется в Jira Markdown."""
        card = ExplainCard(
            event_type="new_edge",
            title="Test",
            what_changed="Change",
            why_risk=["Risk 1", "Risk 2"],
            affected=["svc1", "svc2"],
            recommendation="Fix",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
            rules_triggered=[],
        )

        desc = self.client.format_description(card)

        # Check Jira Markdown headers
        self.assertIn("h2. What Changed", desc)
        self.assertIn("h2. Why Risk", desc)
        self.assertIn("h2. Affected Services", desc)
        self.assertIn("h2. Recommendation", desc)
        self.assertIn("* Risk 1", desc)
        self.assertIn("* Risk 2", desc)

    def test_get_priority(self):
        """Priority mapping работает."""
        self.assertEqual(self.client.get_priority("critical"), "Highest")
        self.assertEqual(self.client.get_priority("high"), "High")
        self.assertEqual(self.client.get_priority("medium"), "Medium")
        self.assertEqual(self.client.get_priority("low"), "Low")

    @patch("integrations.jira_client.requests.post")
    def test_create_issue(self, mock_post):
        """Создание issue работает."""
        mock_post.return_value.json.return_value = {"key": "TEST-123"}
        mock_post.return_value.raise_for_status = Mock()

        card = ExplainCard(
            event_type="new_edge",
            title="Test",
            what_changed="Test",
            why_risk=["Test"],
            affected=["svc1"],
            recommendation="Test",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
            rules_triggered=[],
        )

        result = self.client.create_issue(card)

        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["issue_key"], "TEST-123")
        self.assertIn("issue_url", result)
        mock_post.assert_called_once()

    def test_deduplication(self):
        """Дедупликация работает."""
        self.client._open_issues["svc1->svc2"] = "TEST-123"

        card = ExplainCard(
            event_type="new_edge",
            title="Test",
            what_changed="Test",
            why_risk=["Test"],
            affected=["svc1"],
            recommendation="Test",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
            rules_triggered=[],
        )

        result = self.client.create_issue(card)

        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["issue_key"], "TEST-123")


class TestSIEMExporter(unittest.TestCase):
    """Тесты SIEM exporter."""

    def setUp(self):
        self.exporter = SIEMExporter(transport="syslog")

    def test_format_cef(self):
        """CEF format валиден."""
        card = ExplainCard(
            event_type="new_edge",
            title="Test Event",
            what_changed="Test change",
            why_risk=["Risk"],
            affected=["svc1", "svc2"],
            recommendation="Fix",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
            rules_triggered=[],
        )

        cef = self.exporter.format_cef(card)

        # Check CEF structure: CEF:0|Vendor|Product|Version|SignatureID|Name|Severity|Extension
        self.assertTrue(cef.startswith("CEF:0|"))

        parts = cef.split("|")
        self.assertEqual(len(parts), 8)  # 7 pipe-separated parts + extensions

        # Check fields
        self.assertEqual(parts[1], "SecureGuardDrift")  # Vendor
        self.assertEqual(parts[4], "new_edge")  # SignatureID
        self.assertEqual(parts[6], "10")  # Severity (critical = 10)

        # Check extensions
        extensions = parts[7]
        self.assertIn("src=svc1", extensions)
        self.assertIn("dst=svc2", extensions)
        self.assertIn("cs1=85", extensions)  # risk_score


class TestNotificationRouter(unittest.TestCase):
    """Тесты notification router."""

    def test_get_targets_for_severity(self):
        """Router маршрутизирует по правилам."""
        settings = IntegrationsSettings(
            router_critical_targets="slack,jira",
            router_high_targets="slack",
            router_medium_targets="siem",
            router_low_targets="",
        )

        router = NotificationRouter(settings)

        self.assertEqual(router.get_targets_for_severity("critical"), ["slack", "jira"])
        self.assertEqual(router.get_targets_for_severity("high"), ["slack"])
        self.assertEqual(router.get_targets_for_severity("medium"), ["siem"])
        self.assertEqual(router.get_targets_for_severity("low"), [])


if __name__ == "__main__":
    unittest.main()
