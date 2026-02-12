"""Week 1 integration test: generate → parse → build → save → load."""

import csv
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.generate_mock_data import generate_rows, CSV_HEADER
from collector.ingress_parser import parse_log_file, get_time_windows, filter_by_time_window
from graph.builder import build_snapshot
from graph.storage import SnapshotStore

HOURS = 3
START = datetime(2026, 1, 1, 0, 0, 0)


class TestWeek1Integration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 1. Generate mock CSV into a temp file
        cls._csv_fd, cls.csv_path = tempfile.mkstemp(suffix=".csv")
        rows = generate_rows(START, HOURS)
        with open(cls.csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CSV_HEADER)
            w.writerows(rows)

        # 2. Parse
        cls.records = parse_log_file(cls.csv_path)

        # 3. Time windows
        cls.windows = get_time_windows(cls.records, window_hours=1)

        # 4-5. Build snapshots & save to temp DB
        cls._db_fd, cls.db_path = tempfile.mkstemp(suffix=".db")
        cls.store = SnapshotStore(cls.db_path)
        cls.snapshots = []
        for s, e in cls.windows:
            chunk = filter_by_time_window(cls.records, s, e)
            snap = build_snapshot(chunk, s, e)
            cls.store.save_snapshot(snap)
            cls.snapshots.append(snap)

    @classmethod
    def tearDownClass(cls):
        os.close(cls._csv_fd)
        os.unlink(cls.csv_path)
        try:
            os.close(cls._db_fd)
        except OSError:
            pass
        try:
            os.unlink(cls.db_path)
        except PermissionError:
            pass  # Windows: SQLite may hold the file lock

    # --- assertions ---

    def test_snapshot_count_equals_hours(self):
        self.assertEqual(len(self.snapshots), HOURS)

    def test_each_snapshot_has_edges_and_nodes(self):
        for snap in self.snapshots:
            self.assertGreater(len(snap.edges), 0)
            self.assertGreater(len(snap.nodes), 0)

    def test_hour1_no_order_payments_db(self):
        keys = {e.edge_key() for e in self.snapshots[0].edges}
        self.assertNotIn(("order-svc", "payments-db"), keys)

    def test_hour3_has_order_payments_db(self):
        keys = {e.edge_key() for e in self.snapshots[2].edges}
        self.assertIn(("order-svc", "payments-db"), keys)

    def test_hour3_inventory_error_rate(self):
        edge = next(
            e for e in self.snapshots[2].edges
            if e.edge_key() == ("order-svc", "inventory-svc")
        )
        self.assertGreater(edge.error_rate(), 0.10)

    def test_load_snapshot_matches_original(self):
        orig = self.snapshots[0]
        loaded = self.store.load_snapshot(orig.snapshot_id)
        self.assertIsNotNone(loaded)
        orig_keys = sorted(e.edge_key() for e in orig.edges)
        load_keys = sorted(e.edge_key() for e in loaded.edges)
        self.assertEqual(orig_keys, load_keys)
        self.assertEqual(len(orig.nodes), len(loaded.nodes))

    def test_get_latest_two(self):
        pair = self.store.get_latest_two()
        self.assertIsNotNone(pair)
        prev, latest = pair
        self.assertLess(prev.timestamp_start, latest.timestamp_start)
        self.assertEqual(latest.snapshot_id, self.snapshots[-1].snapshot_id)
        self.assertEqual(prev.snapshot_id, self.snapshots[-2].snapshot_id)


if __name__ == "__main__":
    unittest.main()
