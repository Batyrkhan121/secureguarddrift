"""Tests for GNN feature extraction and dataset conversion."""

import math
import unittest

import numpy as np

from ml.gnn.features import extract_edge_features, extract_node_features
from ml.gnn.dataset import DriftDataset


def _make_snapshot(nodes=None, edges=None, snap_id="snap-1", ts="2025-01-01T00:00:00"):
    return {
        "id": snap_id,
        "timestamp_start": ts,
        "timestamp_end": ts,
        "nodes": nodes or [],
        "edges": edges or [],
    }


SAMPLE_NODES = [
    {"name": "api-gw", "namespace": "default", "node_type": "gateway"},
    {"name": "user-svc", "namespace": "default", "node_type": "service"},
    {"name": "order-svc", "namespace": "default", "node_type": "service"},
    {"name": "user-db", "namespace": "default", "node_type": "database"},
]

SAMPLE_EDGES = [
    {"source": "api-gw", "destination": "user-svc", "request_count": 1000,
     "error_count": 10, "error_rate": 0.01, "avg_latency_ms": 50.0, "p99_latency_ms": 200.0},
    {"source": "api-gw", "destination": "order-svc", "request_count": 500,
     "error_count": 25, "error_rate": 0.05, "avg_latency_ms": 100.0, "p99_latency_ms": 400.0},
    {"source": "user-svc", "destination": "user-db", "request_count": 800,
     "error_count": 5, "error_rate": 0.00625, "avg_latency_ms": 20.0, "p99_latency_ms": 80.0},
]


class TestExtractNodeFeatures(unittest.TestCase):
    def test_basic_extraction(self):
        snap = _make_snapshot(SAMPLE_NODES, SAMPLE_EDGES)
        feats = extract_node_features(snap)
        self.assertEqual(len(feats), 4)
        for name, vec in feats.items():
            self.assertEqual(len(vec), 8, f"Node {name} should have 8 features")

    def test_feature_dimensions(self):
        snap = _make_snapshot(SAMPLE_NODES, SAMPLE_EDGES)
        feats = extract_node_features(snap)
        gw = feats["api-gw"]
        self.assertAlmostEqual(gw[2], 0.0)  # is_service=0
        self.assertAlmostEqual(gw[3], 0.0)  # is_database=0
        self.assertAlmostEqual(gw[4], 1.0)  # is_gateway=1

        svc = feats["user-svc"]
        self.assertAlmostEqual(svc[2], 1.0)  # is_service=1
        self.assertAlmostEqual(svc[3], 0.0)  # is_database=0

        db = feats["user-db"]
        self.assertAlmostEqual(db[3], 1.0)  # is_database=1

    def test_degree_normalization(self):
        snap = _make_snapshot(SAMPLE_NODES, SAMPLE_EDGES)
        feats = extract_node_features(snap)
        gw = feats["api-gw"]
        self.assertAlmostEqual(gw[0], 0.0)  # in_degree=0 (no incoming)
        self.assertGreater(gw[1], 0.0)       # out_degree>0

    def test_empty_snapshot(self):
        snap = _make_snapshot([], [])
        feats = extract_node_features(snap)
        self.assertEqual(len(feats), 0)

    def test_isolated_node(self):
        snap = _make_snapshot(
            [{"name": "lonely", "namespace": "default", "node_type": "service"}],
            [],
        )
        feats = extract_node_features(snap)
        self.assertEqual(len(feats), 1)
        vec = feats["lonely"]
        self.assertEqual(len(vec), 8)
        self.assertAlmostEqual(vec[0], 0.0)  # no incoming
        self.assertAlmostEqual(vec[1], 0.0)  # no outgoing
        self.assertAlmostEqual(vec[5], 0.0)  # no error rates
        self.assertAlmostEqual(vec[6], 0.0)


class TestExtractEdgeFeatures(unittest.TestCase):
    def test_basic_extraction(self):
        edge = SAMPLE_EDGES[0]
        feats = extract_edge_features(edge)
        self.assertEqual(len(feats), 10)

    def test_log_normalization(self):
        edge = SAMPLE_EDGES[0]
        feats = extract_edge_features(edge)
        self.assertAlmostEqual(feats[0], math.log1p(1000))  # request_count
        self.assertAlmostEqual(feats[1], 0.01)                # error_rate
        self.assertAlmostEqual(feats[2], math.log1p(10))      # error_count

    def test_new_edge_flag(self):
        edge = SAMPLE_EDGES[0]
        feats_old = extract_edge_features(edge, is_new=False)
        feats_new = extract_edge_features(edge, is_new=True)
        self.assertAlmostEqual(feats_old[5], 0.0)
        self.assertAlmostEqual(feats_new[5], 1.0)

    def test_baseline_z_scores(self):
        edge = SAMPLE_EDGES[0]
        baseline = {
            "mean_request_count": 900, "std_request_count": 100,
            "mean_error_rate": 0.01, "std_error_rate": 0.005,
            "mean_p99_latency": 180, "std_p99_latency": 20,
        }
        feats = extract_edge_features(edge, baseline=baseline)
        self.assertAlmostEqual(feats[6], (1000 - 900) / 100)  # z_req = 1.0
        self.assertAlmostEqual(feats[7], (0.01 - 0.01) / 0.005)  # z_err = 0.0
        self.assertAlmostEqual(feats[8], (200 - 180) / 20)    # z_lat = 1.0

    def test_no_baseline_zeros(self):
        edge = SAMPLE_EDGES[0]
        feats = extract_edge_features(edge, baseline=None)
        self.assertAlmostEqual(feats[6], 0.0)
        self.assertAlmostEqual(feats[7], 0.0)
        self.assertAlmostEqual(feats[8], 0.0)

    def test_no_nan_values(self):
        edge = {"source": "a", "destination": "b"}
        feats = extract_edge_features(edge)
        for i, v in enumerate(feats):
            self.assertFalse(math.isnan(v), f"Feature {i} is NaN")


class TestDriftDataset(unittest.TestCase):
    def _make_snapshots(self):
        s1 = _make_snapshot(SAMPLE_NODES, SAMPLE_EDGES[:2], "s1", "2025-01-01T00:00:00")
        s2 = _make_snapshot(SAMPLE_NODES, SAMPLE_EDGES, "s2", "2025-01-01T01:00:00")
        s3 = _make_snapshot(SAMPLE_NODES, SAMPLE_EDGES, "s3", "2025-01-01T02:00:00")
        return [s1, s2, s3]

    def test_to_numpy(self):
        snaps = self._make_snapshots()
        ds = DriftDataset(snaps)
        data = ds.to_numpy(baseline=snaps[0], current=snaps[1])
        self.assertEqual(data["x"].shape[1], 8)
        self.assertEqual(data["edge_attr"].shape[1], 10)
        self.assertEqual(data["edge_index"].shape[0], 2)
        self.assertEqual(len(data["y"]), data["edge_attr"].shape[0])

    def test_labels_applied(self):
        snaps = self._make_snapshots()
        labels = {"user-svc->user-db": "anomalous"}
        ds = DriftDataset(snaps, labels=labels)
        data = ds.to_numpy(baseline=snaps[0], current=snaps[1])
        edge_keys = [
            f"{SAMPLE_EDGES[i]['source']}->{SAMPLE_EDGES[i]['destination']}"
            for i in range(len(SAMPLE_EDGES))
        ]
        for i, key in enumerate(edge_keys):
            if key == "user-svc->user-db":
                self.assertEqual(data["y"][i], 1)
            else:
                self.assertEqual(data["y"][i], 0)

    def test_new_edge_detected(self):
        snaps = self._make_snapshots()
        ds = DriftDataset(snaps)
        data = ds.to_numpy(baseline=snaps[0], current=snaps[1])
        # snaps[0] has 2 edges, snaps[1] has 3 → edge[2] is new
        self.assertAlmostEqual(data["edge_attr"][2][5], 1.0)  # is_new flag

    def test_train_test_split(self):
        snaps = self._make_snapshots()
        ds = DriftDataset(snaps)
        train, test = ds.train_test_split(test_ratio=0.2)
        self.assertEqual(len(train) + len(test), 3)
        self.assertGreater(len(train), 0)
        # Last snapshot should be in test set
        self.assertEqual(test[-1]["id"], "s3")

    def test_sorted_by_timestamp(self):
        s1 = _make_snapshot([], [], "s1", "2025-01-01T02:00:00")
        s2 = _make_snapshot([], [], "s2", "2025-01-01T01:00:00")
        ds = DriftDataset([s1, s2])
        self.assertEqual(ds.snapshots[0]["id"], "s2")
        self.assertEqual(ds.snapshots[1]["id"], "s1")

    def test_empty_edges(self):
        snap = _make_snapshot(SAMPLE_NODES, [])
        ds = DriftDataset([snap])
        data = ds.to_numpy(baseline=snap, current=snap)
        self.assertEqual(data["edge_attr"].shape, (0, 10))
        self.assertEqual(len(data["y"]), 0)

    def test_baselines_used(self):
        snaps = self._make_snapshots()
        baselines = {
            "api-gw->user-svc": {
                "mean_request_count": 900, "std_request_count": 100,
                "mean_error_rate": 0.01, "std_error_rate": 0.005,
                "mean_p99_latency": 180, "std_p99_latency": 20,
            }
        }
        ds = DriftDataset(snaps, baselines=baselines)
        data = ds.to_numpy(baseline=snaps[0], current=snaps[1])
        # First edge (api-gw->user-svc) should have z-scores
        self.assertNotAlmostEqual(data["edge_attr"][0][6], 0.0)


if __name__ == "__main__":
    unittest.main()
