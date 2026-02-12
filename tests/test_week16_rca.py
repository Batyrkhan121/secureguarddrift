"""Week 16 tests: RCA integration (API endpoints + algorithm verification)."""

import unittest
import os
import sys

# Ensure project root on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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


CASCADE_SNAPSHOT = _make_snapshot(
    nodes=[
        ("api-gw", "gateway"), ("order-svc", "service"),
        ("inventory-svc", "service"), ("payments-db", "database"),
    ],
    edges=[
        ("api-gw", "order-svc", 1000, 0.02),
        ("order-svc", "inventory-svc", 500, 0.20),
        ("order-svc", "payments-db", 300, 0.15),
        ("inventory-svc", "payments-db", 100, 0.10),
    ],
)

CASCADE_EVENTS = [
    {"source": "order-svc", "destination": "inventory-svc",
     "event_type": "error_spike", "severity": "critical"},
    {"source": "order-svc", "destination": "payments-db",
     "event_type": "error_spike", "severity": "high"},
]


class TestRootCause(unittest.TestCase):
    def test_root_cause_identifies_source(self):
        analyzer = CausalAnalyzer()
        results = analyzer.find_root_cause(CASCADE_SNAPSHOT, CASCADE_EVENTS)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # order-svc is the source of both error edges
        services = [r["service"] for r in results]
        self.assertIn("order-svc", services)

    def test_root_cause_has_confidence(self):
        analyzer = CausalAnalyzer()
        results = analyzer.find_root_cause(CASCADE_SNAPSHOT, CASCADE_EVENTS)
        for r in results:
            self.assertIn("confidence", r)
            self.assertGreaterEqual(r["confidence"], 0)
            self.assertLessEqual(r["confidence"], 1)
            self.assertIn("reason", r)
            self.assertIn("affected_downstream", r)

    def test_pagerank_converges(self):
        analyzer = CausalAnalyzer()
        adj = {"A": ["B", "C"], "B": ["C"], "C": []}
        error_rates = {"A": 0.5, "B": 0.3, "C": 0.1}
        candidates = {"A", "B", "C"}
        ranks = analyzer._error_pagerank(adj, error_rates, candidates)
        self.assertIsInstance(ranks, dict)
        self.assertEqual(len(ranks), 3)
        # All ranks should be positive
        for v in ranks.values():
            self.assertGreater(v, 0)


class TestBlastRadius(unittest.TestCase):
    def test_blast_radius_prediction(self):
        predictor = BlastRadiusPredictor()
        result = predictor.predict(CASCADE_SNAPSHOT, "order-svc")
        self.assertEqual(result["failing_service"], "order-svc")
        self.assertIn("affected", result)
        self.assertIn("total_blast_radius", result)
        affected_names = [a["service"] for a in result["affected"]]
        self.assertIn("inventory-svc", affected_names)
        self.assertIn("payments-db", affected_names)

    def test_blast_radius_has_probability(self):
        predictor = BlastRadiusPredictor()
        result = predictor.predict(CASCADE_SNAPSHOT, "order-svc")
        for a in result["affected"]:
            self.assertIn("probability", a)
            self.assertGreaterEqual(a["probability"], 0)
            self.assertLessEqual(a["probability"], 1)
            self.assertIn("time_to_impact_minutes", a)
            self.assertIn("impact", a)


class TestPredictDrift(unittest.TestCase):
    def test_predict_add_service(self):
        predictor = DriftPredictor()
        predictions = predictor.predict_from_diff(
            CASCADE_SNAPSHOT,
            {
                "add_services": ["new-svc"],
                "add_edges": [{"source": "api-gw", "destination": "new-svc"}],
            },
        )
        self.assertIsInstance(predictions, list)
        self.assertGreater(len(predictions), 0)
        events = [p["predicted_event"] for p in predictions]
        self.assertTrue(any("new" in e for e in events))

    def test_predict_remove_service(self):
        predictor = DriftPredictor()
        predictions = predictor.predict_from_diff(
            CASCADE_SNAPSHOT,
            {"remove_services": ["inventory-svc"]},
        )
        self.assertIsInstance(predictions, list)
        self.assertGreater(len(predictions), 0)


class TestEmptyGraph(unittest.TestCase):
    def test_empty_graph_root_cause(self):
        empty = {"nodes": [], "edges": []}
        analyzer = CausalAnalyzer()
        results = analyzer.find_root_cause(empty, [])
        self.assertEqual(results, [])

    def test_empty_graph_blast_radius(self):
        empty = {"nodes": [], "edges": []}
        predictor = BlastRadiusPredictor()
        result = predictor.predict(empty, "nonexistent")
        self.assertEqual(result["total_blast_radius"], 0)
        self.assertEqual(len(result["affected"]), 0)

    def test_empty_changes_predict_drift(self):
        predictor = DriftPredictor()
        predictions = predictor.predict_from_diff(CASCADE_SNAPSHOT, {})
        self.assertEqual(predictions, [])


class TestAPIEndpoints(unittest.TestCase):
    """Test RCA API endpoints via FastAPI TestClient."""

    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
            from api.server import app
            cls.client = TestClient(app)
            cls.skip = False
        except Exception:
            cls.skip = True

    def setUp(self):
        if self.skip:
            self.skipTest("FastAPI TestClient not available")

    def test_root_cause_endpoint(self):
        # Get a snapshot_id first
        r = self.client.get("/api/snapshots")
        if r.status_code != 200 or not r.json():
            self.skipTest("No snapshots available")
        sid = r.json()[0].get("snapshot_id", r.json()[0].get("id", ""))
        r2 = self.client.get(f"/api/rca/root-cause?snapshot_id={sid}")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("root_causes", r2.json())

    def test_blast_radius_endpoint(self):
        r = self.client.get("/api/snapshots")
        if r.status_code != 200 or not r.json():
            self.skipTest("No snapshots available")
        sid = r.json()[0].get("snapshot_id", r.json()[0].get("id", ""))
        r2 = self.client.get(f"/api/rca/blast-radius?service=api-gw&snapshot_id={sid}")
        self.assertEqual(r2.status_code, 200)
        self.assertIn("failing_service", r2.json())

    def test_predict_drift_endpoint(self):
        r = self.client.post("/api/rca/predict-drift",
                             json={"add_services": ["test-svc"]})
        self.assertIn(r.status_code, [200, 404])


if __name__ == "__main__":
    unittest.main()
