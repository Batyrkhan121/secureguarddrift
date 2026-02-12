# tests/test_week6_policies.py
# Тесты для NetworkPolicy генератора (Неделя 6)

import unittest
import yaml
from drift.explainer import ExplainCard
from policy.generator import generate_policies, PolicySuggestion
from policy.renderer import to_yaml, to_markdown, to_json
from policy.storage import PolicyStore
import tempfile
import os


class TestPolicyGenerator(unittest.TestCase):
    """Тесты генератора policies."""

    def test_new_edge_to_database_generates_deny_policy(self):
        """new_edge к database → генерирует deny policy."""
        card = ExplainCard(
            event_type="new_edge",
            title="Новая связь: order-svc -> payments-db",
            what_changed="Появилась новая связь order-svc -> payments-db",
            why_risk=["Прямой доступ к БД минуя владельца"],
            affected=["order-svc", "payments-db"],
            recommendation="Блокировать прямой доступ",
            risk_score=85,
            severity="critical",
            source="order-svc",
            destination="payments-db",
            rules_triggered=["database_direct_access"],
        )

        policies = generate_policies([card])

        self.assertEqual(len(policies), 1)
        self.assertIn("deny-db", policies[0].policy_id)
        self.assertEqual(policies[0].severity, "critical")
        self.assertEqual(policies[0].source, "order-svc")
        self.assertEqual(policies[0].destination, "payments-db")

    def test_bypass_gateway_generates_restrict_policy(self):
        """bypass_gateway → генерирует restrict policy."""
        card = ExplainCard(
            event_type="new_edge",
            title="Новая связь: user-app -> auth-svc",
            what_changed="Появилась связь в обход gateway",
            why_risk=["Обход api-gateway"],
            affected=["user-app", "auth-svc"],
            recommendation="Разрешить только через gateway",
            risk_score=75,
            severity="high",
            source="user-app",
            destination="auth-svc",
            rules_triggered=["bypass_gateway"],
        )

        policies = generate_policies([card])

        self.assertEqual(len(policies), 1)
        self.assertIn("restrict", policies[0].policy_id)
        self.assertIn("gateway", policies[0].policy_id)
        self.assertEqual(policies[0].severity, "high")

    def test_low_severity_no_policy(self):
        """low severity → не генерирует policy."""
        card = ExplainCard(
            event_type="new_edge",
            title="Новая связь",
            what_changed="Новая связь",
            why_risk=["Изменение"],
            affected=["svc1", "svc2"],
            recommendation="Проверить",
            risk_score=30,
            severity="low",
            source="svc1",
            destination="svc2",
            rules_triggered=[],
        )

        policies = generate_policies([card])

        self.assertEqual(len(policies), 0)


class TestPolicyRenderer(unittest.TestCase):
    """Тесты рендеринга policies."""

    def test_yaml_is_valid(self):
        """YAML валиден (парсится yaml.safe_load)."""
        from policy.templates import deny_database_direct

        policy_dict = deny_database_direct("payments-db", ["payment-svc"])
        suggestion = PolicySuggestion(
            policy_id="test-policy",
            yaml_dict=policy_dict,
            reason="Test reason",
            risk_score=85,
            severity="critical",
            source="order-svc",
            destination="payments-db",
        )

        yaml_text = to_yaml(suggestion)

        # Проверяем, что YAML валиден
        parsed = yaml.safe_load(yaml_text)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["kind"], "NetworkPolicy")
        self.assertEqual(parsed["apiVersion"], "networking.k8s.io/v1")

    def test_markdown_contains_key_info(self):
        """Markdown содержит ключевую информацию."""
        suggestion = PolicySuggestion(
            policy_id="test-policy",
            yaml_dict={},
            reason="Test reason",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
        )

        md = to_markdown(suggestion)

        self.assertIn("test-policy", md)
        self.assertIn("CRITICAL", md)
        self.assertIn("svc1", md)
        self.assertIn("svc2", md)

    def test_json_is_valid(self):
        """JSON валиден."""
        import json

        suggestion = PolicySuggestion(
            policy_id="test-policy",
            yaml_dict={},
            reason="Test reason",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
        )

        json_text = to_json(suggestion)

        # Проверяем, что JSON валиден
        parsed = json.loads(json_text)
        self.assertEqual(parsed["policy_id"], "test-policy")
        self.assertEqual(parsed["severity"], "critical")


class TestPolicyStorage(unittest.TestCase):
    """Тесты хранилища policies."""

    def setUp(self):
        """Создаем временную БД для тестов."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.store = PolicyStore(self.temp_db.name)

    def tearDown(self):
        """Удаляем временную БД."""
        os.unlink(self.temp_db.name)

    def test_save_and_list_policies(self):
        """Сохранение и получение списка policies."""
        suggestion = PolicySuggestion(
            policy_id="test-policy-1",
            yaml_dict={"kind": "NetworkPolicy"},
            reason="Test reason",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
        )

        self.store.save_policy(suggestion)
        policies = self.store.list_policies()

        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0]["policy_id"], "test-policy-1")

    def test_approve_changes_status(self):
        """Approve меняет статус на approved."""
        suggestion = PolicySuggestion(
            policy_id="test-policy-1",
            yaml_dict={},
            reason="Test",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
        )

        self.store.save_policy(suggestion)
        success = self.store.update_status("test-policy-1", "approved")

        self.assertTrue(success)
        policy = self.store.get_policy("test-policy-1")
        self.assertEqual(policy["status"], "approved")

    def test_reject_changes_status(self):
        """Reject меняет статус на rejected."""
        suggestion = PolicySuggestion(
            policy_id="test-policy-1",
            yaml_dict={},
            reason="Test",
            risk_score=85,
            severity="critical",
            source="svc1",
            destination="svc2",
        )

        self.store.save_policy(suggestion)
        success = self.store.update_status("test-policy-1", "rejected")

        self.assertTrue(success)
        policy = self.store.get_policy("test-policy-1")
        self.assertEqual(policy["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
