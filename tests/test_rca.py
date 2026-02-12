"""Tests for Root Cause Analysis module."""

import unittest

from ml.rca.causal import CausalAnalyzer
from ml.rca.blast_radius import BlastRadiusPredictor
from ml.rca.predictor import DriftPredictor


def _make_snapshot(nodes, edges):
    return {
        "nodes": [{"name": n, "node_type": t, "namespace": "default"} for n, t in nodes],
        "edges": [
            {
                "source": s, "destination": d,
                "request_count": rc, "error_rate": er, "error_count": int(rc * er),
                "avg_latency_ms": 50.0, "p99_latency_ms": 100.0,
            }
            for s, d, rc, er in edges
        ],
    }


SNAPSHOT = _make_snapshot(
    nodes=[
        ("api-gw", "gateway"), ("order-svc", "service"),
        ("inventory-svc", "service"), ("payments-db", "database"),
        ("user-svc", "service"),
    ],
    edges=[
        ("api-gw", "order-svc", 1000, 0.01),
        ("order-svc", "inventory-svc", 500, 0.15),
        ("order-svc", "payments-db", 300, 0.08),
        ("inventory-svc", "payments-db", 100, 0.02),
        ("api-gw", "user-svc", 800, 0.005),
    ],
)

ERROR_EVENTS = [
    {"source": "order-svc", "destination": "inventory-svc",
     "event_type": "error_spike", "severity": "high"},
    {"source": "order-svc", "destination": "payments-db",
     "event_type": "error_spike", "severity": "critical"},
]


class TestCausalAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CausalAnalyzer()

    def test_find_root_cause_returns_list(self):
        result = self.analyzer.find_root_cause(SNAPSHOT, ERROR_EVENTS)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_root_cause_has_required_fields(self):
        result = self.analyzer.find_root_cause(SNAPSHOT, ERROR_EVENTS)
        for candidate in result:
            self.assertIn("service", candidate)
            self.assertIn("confidence", candidate)
            self.assertIn("reason", candidate)
            self.assertIn("affected_downstream", candidate)
            self.assertIn("evidence", candidate)

    def test_confidence_between_0_and_1(self):
        result = self.analyzer.find_root_cause(SNAPSHOT, ERROR_EVENTS)
        for candidate in result:
            self.assertGreaterEqual(candidate["confidence"], 0)
            self.assertLessEqual(candidate["confidence"], 1)

    def test_max_3_candidates(self):
        result = self.analyzer.find_root_cause(SNAPSHOT, ERROR_EVENTS)
        self.assertLessEqual(len(result), 3)

    def test_empty_events(self):
        result = self.analyzer.find_root_cause(SNAPSHOT, [])
        self.assertEqual(result, [])

    def test_empty_snapshot(self):
        result = self.analyzer.find_root_cause({"nodes": [], "edges": []}, ERROR_EVENTS)
        self.assertEqual(result, [])

    def test_pagerank_converges(self):
        adj = {"A": ["B", "C"], "B": ["C"], "C": []}
        rates = {"A": 0.5, "B": 0.3, "C": 0.1}
        scores = self.analyzer._error_pagerank(adj, rates, {"A", "B", "C"})
        self.assertEqual(len(scores), 3)
        for v in scores.values():
            self.assertGreater(v, 0)

    def test_order_svc_is_likely_root_cause(self):
        result = self.analyzer.find_root_cause(SNAPSHOT, ERROR_EVENTS)
        services = [r["service"] for r in result]
        self.assertIn("order-svc", services)


class TestBlastRadiusPredictor(unittest.TestCase):
    def setUp(self):
        self.predictor = BlastRadiusPredictor()

    def test_predict_returns_dict(self):
        result = self.predictor.predict(SNAPSHOT, "order-svc")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["failing_service"], "order-svc")

    def test_predict_has_required_fields(self):
        result = self.predictor.predict(SNAPSHOT, "order-svc")
        self.assertIn("affected", result)
        self.assertIn("total_blast_radius", result)
        self.assertIn("estimated_recovery_minutes", result)
        self.assertIn("failure_mode", result)

    def test_affected_services_have_fields(self):
        result = self.predictor.predict(SNAPSHOT, "order-svc")
        for svc in result["affected"]:
            self.assertIn("service", svc)
            self.assertIn("probability", svc)
            self.assertIn("time_to_impact_minutes", svc)
            self.assertIn("impact", svc)

    def test_unknown_service_returns_empty(self):
        result = self.predictor.predict(SNAPSHOT, "nonexistent")
        self.assertEqual(result["total_blast_radius"], 0)
        self.assertEqual(result["affected"], [])

    def test_order_svc_affects_downstream(self):
        result = self.predictor.predict(SNAPSHOT, "order-svc")
        affected_names = [a["service"] for a in result["affected"]]
        self.assertIn("inventory-svc", affected_names)
        self.assertIn("payments-db", affected_names)

    def test_probability_between_0_and_1(self):
        result = self.predictor.predict(SNAPSHOT, "api-gw")
        for svc in result["affected"]:
            self.assertGreaterEqual(svc["probability"], 0)
            self.assertLessEqual(svc["probability"], 1)


class TestDriftPredictor(unittest.TestCase):
    def setUp(self):
        self.predictor = DriftPredictor()

    def test_add_service(self):
        changes = {"add_services": ["new-svc"]}
        result = self.predictor.predict_from_diff(SNAPSHOT, changes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["predicted_event"], "new_service")
        self.assertEqual(result[0]["source"], "new-svc")

    def test_remove_service(self):
        changes = {"remove_services": ["order-svc"]}
        result = self.predictor.predict_from_diff(SNAPSHOT, changes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["predicted_event"], "removed_service")
        self.assertIn(result[0]["predicted_severity"], ("high", "critical"))

    def test_add_edge(self):
        changes = {"add_edges": [{"source": "user-svc", "destination": "payments-db"}]}
        result = self.predictor.predict_from_diff(SNAPSHOT, changes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["predicted_event"], "new_edge")

    def test_config_change(self):
        changes = {"modify_configs": [{"service": "order-svc", "type": "replicas"}]}
        result = self.predictor.predict_from_diff(SNAPSHOT, changes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["predicted_event"], "config_change")
        self.assertEqual(result[0]["predicted_severity"], "high")

    def test_empty_changes(self):
        result = self.predictor.predict_from_diff(SNAPSHOT, {})
        self.assertEqual(result, [])

    def test_combined_changes(self):
        changes = {
            "add_services": ["new-svc"],
            "add_edges": [{"source": "new-svc", "destination": "order-svc"}],
        }
        result = self.predictor.predict_from_diff(SNAPSHOT, changes)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
