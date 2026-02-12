"""tests/test_smoke.py — Full MVP smoke test: pipeline → API → 14 assertions."""
import csv
import os
import shutil
import tempfile
import unittest
from datetime import datetime
try:
    from scripts.generate_mock_data import generate_rows, CSV_HEADER
    _HAS_GEN = True
except ImportError:
    _HAS_GEN = False

class TestSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        db, cp = os.path.join(cls._tmp, "s.db"), os.path.join(cls._tmp, "s.csv")
        if _HAS_GEN:
            rows = generate_rows(datetime(2026, 2, 10, 10, 0, 0), 3)
            with open(cp, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(CSV_HEADER)
                w.writerows(rows)
        else:
            import subprocess
            import sys
            subprocess.run([sys.executable, "-m", "scripts.generate_mock_data",
                            "--output", cp, "--hours", "3"], check=True)
        from collector.ingress_parser import parse_log_file, get_time_windows, filter_by_time_window
        from graph.builder import build_snapshot
        from graph.storage import SnapshotStore
        recs = parse_log_file(cp)
        store = SnapshotStore(db)
        for s, e in get_time_windows(recs, window_hours=1):
            store.save_snapshot(build_snapshot(filter_by_time_window(recs, s, e), s, e))
        import api.server as srv
        srv.store = store
        for fn in ("init_graph_store", "init_drift_store", "init_report_store"):
            if hasattr(srv, fn):
                getattr(srv, fn)(store)
        from fastapi.testclient import TestClient
        cls.C = TestClient(srv.app)
        cls.snaps = cls.C.get("/api/snapshots").json()
        cls.fid, cls.lid = cls.snaps[0]["snapshot_id"], cls.snaps[-1]["snapshot_id"]
        cls.gf = cls.C.get(f"/api/graph/{cls.fid}").json()
        cls.gl = cls.C.get(f"/api/graph/{cls.lid}").json()
        cls.drift = cls.C.get(f"/api/drift/?baseline_id={cls.fid}&current_id={cls.lid}").json()
        cls.new_edge = next((ev for ev in cls.drift["events"] if ev["event_type"] == "new_edge"
            and ev["source"] == "order-svc" and ev["destination"] == "payments-db"), None)
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)
    @staticmethod
    def _edge_set(g):
        return {(e["source"], e["destination"]) for e in g["edges"]}

    def test_01_health(self):
        self.assertEqual(self.C.get("/api/health").status_code, 200, "Health endpoint failed")
    def test_02_three_snapshots(self):
        self.assertEqual(len(self.snaps), 3, f"Expected 3 snapshots, got {len(self.snaps)}")
    def test_03_first_graph(self):
        self.assertGreater(len(self.gf["nodes"]), 0, "First graph has no nodes")
        self.assertGreater(len(self.gf["edges"]), 0, "First graph has no edges")
    def test_04_last_graph(self):
        self.assertGreater(len(self.gl["nodes"]), 0, "Last graph has no nodes")
        self.assertGreater(len(self.gl["edges"]), 0, "Last graph has no edges")
    def test_05_first_no_anomaly_edge(self):
        self.assertNotIn(("order-svc", "payments-db"), self._edge_set(self.gf),
                         "First snapshot should NOT have order-svc→payments-db")
    def test_06_last_has_anomaly_edge(self):
        self.assertIn(("order-svc", "payments-db"), self._edge_set(self.gl),
                      "Last snapshot should have order-svc→payments-db")
    def test_07_drift_has_events(self):
        self.assertGreaterEqual(len(self.drift["events"]), 1, "Drift returned no events")
    def test_08_new_edge_exists(self):
        self.assertIsNotNone(self.new_edge, "No new_edge event for order-svc→payments-db")
    def test_09_risk_score(self):
        self.assertIsNotNone(self.new_edge, "new_edge not found")
        self.assertGreaterEqual(self.new_edge["risk_score"], 70,
                                f"Risk score too low: {self.new_edge['risk_score']}")
    def test_10_severity(self):
        self.assertIsNotNone(self.new_edge, "new_edge not found")
        self.assertIn(self.new_edge["severity"], ("critical", "high"),
                      f"Unexpected severity: {self.new_edge['severity']}")
    def test_11_why_risk(self):
        self.assertIsNotNone(self.new_edge, "new_edge not found")
        self.assertGreaterEqual(len(self.new_edge["why_risk"]), 2,
                                f"why_risk has only {len(self.new_edge['why_risk'])} items")
    def test_12_recommendation(self):
        self.assertIsNotNone(self.new_edge, "new_edge not found")
        self.assertTrue(self.new_edge["recommendation"], "recommendation is empty")
    def test_13_report_md(self):
        r = self.C.get(f"/api/report/md?baseline_id={self.fid}&current_id={self.lid}")
        self.assertEqual(r.status_code, 200, "Report MD endpoint failed")
        self.assertIn("order-svc", r.text, "MD report missing order-svc")
        self.assertIn("payments-db", r.text, "MD report missing payments-db")
    def test_14_report_json(self):
        d = self.C.get(f"/api/report/json?baseline_id={self.fid}&current_id={self.lid}").json()
        self.assertIsInstance(d, dict, "Report JSON should return a dict")
        self.assertGreater(len(d), 0, "Report JSON should not be empty")

if __name__ == "__main__":
    unittest.main()
