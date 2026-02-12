"""Tests for the extended /api/health endpoint."""
import csv
import os
import shutil
import tempfile
import unittest
from datetime import datetime

from scripts.generate_mock_data import generate_rows, CSV_HEADER


class TestHealthcheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        db = os.path.join(cls._tmp, "s.db")
        cp = os.path.join(cls._tmp, "s.csv")
        rows = generate_rows(datetime(2026, 2, 10, 10, 0, 0), 3)
        with open(cp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_HEADER)
            w.writerows(rows)
        from collector.ingress_parser import parse_log_file, get_time_windows, filter_by_time_window
        from graph.builder import build_snapshot
        from graph.storage import SnapshotStore
        recs = parse_log_file(cp)
        st = SnapshotStore(db)
        for s, e in get_time_windows(recs, window_hours=1):
            st.save_snapshot(build_snapshot(filter_by_time_window(recs, s, e), s, e), tenant_id="default")
        import api.server as srv
        srv.store = st
        from api.routes.graph_routes import init_store as ig
        from api.routes.drift_routes import init_store as id_
        from api.routes.report_routes import init_store as ir
        ig(st)
        id_(st)
        ir(st)
        from fastapi.testclient import TestClient
        cls.C = TestClient(srv.app)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_backward_compat(self):
        d = self.C.get("/api/health").json()
        self.assertEqual(d["status"], "ok")
        self.assertIn("snapshots_count", d)
        self.assertGreaterEqual(d["snapshots_count"], 1)

    def test_new_fields_present(self):
        d = self.C.get("/api/health").json()
        for key in ("version", "uptime_seconds", "last_snapshot_age_seconds",
                     "db_size_bytes", "components", "system"):
            self.assertIn(key, d, f"Missing field: {key}")

    def test_components_structure(self):
        comp = self.C.get("/api/health").json()["components"]
        for name in ("database", "collector", "scheduler"):
            self.assertIn(name, comp)
            self.assertIn("status", comp[name])

    def test_db_latency(self):
        db = self.C.get("/api/health").json()["components"]["database"]
        self.assertEqual(db["status"], "ok")
        self.assertGreaterEqual(db["latency_ms"], 0)

    def test_status_logic_ok(self):
        self.assertEqual(self.C.get("/api/health").json()["status"], "ok")
