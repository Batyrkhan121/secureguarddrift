"""tests/test_week3_api.py — Week 3 API endpoint tests."""
import unittest
from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)
REQUIRED_EVENT_FIELDS = [
    "event_type", "source", "destination", "severity",
    "risk_score", "title", "what_changed", "why_risk",
    "affected", "recommendation",
]

class TestHealth(unittest.TestCase):
    def test_health(self):
        r = client.get("/api/health")
        self.assertEqual(r.status_code, 200, "Health endpoint failed")
        d = r.json()
        self.assertEqual(d["status"], "ok", "Health status is not 'ok'")
        self.assertGreaterEqual(d["snapshots_count"], 1, "No snapshots in DB")

class TestSnapshots(unittest.TestCase):
    def test_snapshots_list(self):
        r = client.get("/api/snapshots")
        self.assertEqual(r.status_code, 200, "Snapshots endpoint failed")
        data = r.json()
        self.assertGreater(len(data), 0, "Snapshots list is empty")
        for s in data:
            self.assertIn("snapshot_id", s, "Snapshot missing snapshot_id")

class TestGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._snapshots = client.get("/api/snapshots").json()
        cls._latest = client.get("/api/graph/latest").json()
    def test_graph_latest(self):
        self.assertGreater(len(self._latest["nodes"]), 0, "Graph has no nodes")
        self.assertGreater(len(self._latest["edges"]), 0, "Graph has no edges")
    def test_graph_by_id(self):
        sid = self._snapshots[0]["snapshot_id"]
        r = client.get(f"/api/graph/{sid}")
        self.assertEqual(r.status_code, 200, f"Graph by ID failed for {sid[:8]}")
        d = r.json()
        self.assertIn("nodes", d, "Response missing 'nodes'")
        self.assertIn("edges", d, "Response missing 'edges'")
    def test_graph_not_found(self):
        r = client.get("/api/graph/fake-id-12345")
        self.assertEqual(r.status_code, 404, f"Expected 404 for fake ID, got {r.status_code}")
    def test_graph_edges_have_error_rate(self):
        for edge in self._latest["edges"]:
            self.assertIn("error_rate", edge,
                          f"Edge {edge.get('source','?')}→{edge.get('destination','?')} missing error_rate")
    def test_graph_nodes_have_type(self):
        for node in self._latest["nodes"]:
            self.assertIn("node_type", node, f"Node {node.get('name','?')} missing node_type")

class TestDrift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = client.get("/api/drift/")
        cls._drift_status = r.status_code
        cls._drift_data = r.json()
    def _get_events(self):
        self.assertEqual(self._drift_status, 200, "Drift API returned non-200")
        return self._drift_data
    def test_drift_default(self):
        d = self._get_events()
        self.assertIn("events", d, "Response missing 'events'")
        self.assertGreaterEqual(d["events_count"], 1, "No drift events detected")
    def test_drift_with_params(self):
        snaps = client.get("/api/snapshots").json()
        if len(snaps) < 2:
            self.skipTest("Need at least 2 snapshots")
        fid, lid = snaps[0]["snapshot_id"], snaps[-1]["snapshot_id"]
        r = client.get(f"/api/drift/?baseline_id={fid}&current_id={lid}")
        self.assertEqual(r.status_code, 200, f"Drift with params failed: {r.status_code}")
        d = r.json()
        self.assertIn("events", d, "Response missing 'events' key")
        self.assertGreater(len(d["events"]), 0, "Drift with params returned no events")
    def test_drift_has_critical(self):
        d = self._get_events()
        sevs = {ev["severity"] for ev in d["events"]}
        self.assertTrue(sevs & {"critical", "high"}, "No critical/high events found")
    def test_drift_event_fields(self):
        d = self._get_events()
        for ev in d["events"]:
            for f in REQUIRED_EVENT_FIELDS:
                self.assertIn(f, ev, f"Missing field: {f}")
    def test_drift_sorted(self):
        d = self._get_events()
        scores = [ev["risk_score"] for ev in d["events"]]
        self.assertEqual(scores, sorted(scores, reverse=True),
                         "Events not sorted by risk_score descending")
    def test_drift_summary(self):
        r = client.get("/api/drift/summary")
        self.assertEqual(r.status_code, 200, "Drift summary endpoint failed")
        d = r.json()
        for key in ("total", "critical", "high", "medium", "low"):
            self.assertIn(key, d, f"Summary missing key: {key}")

class TestReport(unittest.TestCase):
    def test_report_md(self):
        r = client.get("/api/report/md")
        self.assertEqual(r.status_code, 200, "Report MD endpoint failed")
        ct = r.headers["content-type"]
        self.assertTrue("text/markdown" in ct or "text/plain" in ct,
                        f"Unexpected content-type: {ct}")
        self.assertIn("SecureGuard Drift", r.text, "MD report missing title")
    def test_report_json(self):
        r = client.get("/api/report/json")
        self.assertEqual(r.status_code, 200, "Report JSON endpoint failed")
        d = r.json()
        self.assertIsInstance(d, dict, "Report JSON should return a dict")
        self.assertGreater(len(d), 0, "Report JSON should not be empty")

class TestStatic(unittest.TestCase):
    def test_root(self):
        r = client.get("/")
        self.assertEqual(r.status_code, 200, "Root endpoint failed")
        self.assertIn("SecureGuard Drift", r.text, "Root page missing title")

if __name__ == "__main__":
    unittest.main()
