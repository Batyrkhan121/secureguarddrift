"""Week 2 integration test: mock data -> drift detection -> scoring -> explain -> report."""

import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.generate_mock_data import generate_rows, CSV_HEADER
from collector.ingress_parser import parse_log_file, get_time_windows, filter_by_time_window
from graph.builder import build_snapshot
from drift.detector import detect_drift
from drift.scorer import score_all_events
from drift.rules import rule_database_direct_access
from drift.explainer import explain_all
from drift.report import generate_report
from datetime import datetime

HOURS = 3
START = datetime(2026, 1, 1, 0, 0, 0)


class TestWeek2Integration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 1. Generate mock CSV
        cls._csv_fd, cls.csv_path = tempfile.mkstemp(suffix=".csv")
        rows = generate_rows(START, HOURS)
        with open(cls.csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_HEADER)
            w.writerows(rows)

        # 2-3. Parse, build baseline (hour 1) and current (hour 3)
        records = parse_log_file(cls.csv_path)
        windows = get_time_windows(records, window_hours=1)
        h1 = filter_by_time_window(records, *windows[0])
        h3 = filter_by_time_window(records, *windows[2])
        cls.baseline = build_snapshot(h1, *windows[0])
        cls.current = build_snapshot(h3, *windows[2])

        # 4-6. Detect, score, explain
        cls.events = detect_drift(cls.baseline, cls.current)
        cls.scored = score_all_events(cls.events)
        cls.cards = explain_all(cls.scored)

        # 7. Report
        cls._rpt_fd, cls.rpt_path = tempfile.mkstemp(suffix=".md")
        cls.report = generate_report(cls.baseline, cls.current, cls.cards, cls.rpt_path)

    @classmethod
    def tearDownClass(cls):
        os.close(cls._csv_fd)
        os.unlink(cls.csv_path)
        try:
            os.close(cls._rpt_fd)
        except OSError:
            pass
        try:
            os.unlink(cls.rpt_path)
        except PermissionError:
            pass

    def _find(self, etype, src, dst):
        return next((e for e in self.events
                     if e.event_type == etype and e.source == src and e.destination == dst), None)

    def test_new_edge_order_payments_db(self):
        self.assertIsNotNone(self._find("new_edge", "order-svc", "payments-db"))

    def test_new_edge_user_orders_db(self):
        self.assertIsNotNone(self._find("new_edge", "user-svc", "orders-db"))

    def test_error_spike_inventory(self):
        self.assertIsNotNone(self._find("error_spike", "order-svc", "inventory-svc"))

    def test_score_order_payments_db_ge_70(self):
        ev, sc, _ = next(t for t in self.scored
                         if t[0].source == "order-svc" and t[0].destination == "payments-db")
        self.assertGreaterEqual(sc, 70)

    def test_rule_database_direct_access_triggered(self):
        ev = self._find("new_edge", "order-svc", "payments-db")
        result = rule_database_direct_access(ev)
        self.assertTrue(result.triggered)

    def test_report_contains_services(self):
        self.assertIn("order-svc", self.report)
        self.assertIn("payments-db", self.report)

    def test_report_contains_severity(self):
        self.assertTrue("CRITICAL" in self.report or "HIGH" in self.report)

    def test_report_file_exists_and_not_empty(self):
        self.assertTrue(os.path.exists(self.rpt_path))
        self.assertGreater(os.path.getsize(self.rpt_path), 0)


if __name__ == "__main__":
    unittest.main()
