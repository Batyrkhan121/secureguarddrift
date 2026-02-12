"""Dataset conversion for GNN-based anomaly detection."""

from __future__ import annotations

from typing import Any

import numpy as np

from ml.gnn.features import extract_edge_features, extract_node_features

try:
    import torch
    from torch_geometric.data import Data as PyGData

    HAS_PYG = True
except ImportError:
    HAS_PYG = False


class DriftDataset:
    """Convert snapshot pairs + feedback labels into graph data objects.

    Args:
        snapshots: List of snapshot dicts sorted by timestamp_start.
        labels: Mapping of edge keys ("source->destination") to
                "normal" or "anomalous" from the feedback table.
        baselines: Mapping of edge keys to baseline stats dicts.
    """

    def __init__(
        self,
        snapshots: list[dict],
        labels: dict[str, str] | None = None,
        baselines: dict[str, dict] | None = None,
    ):
        self.snapshots = sorted(
            snapshots, key=lambda s: s.get("timestamp_start", "")
        )
        self.labels = labels or {}
        self.baselines = baselines or {}

    def to_pyg(self, baseline: dict, current: dict) -> Any:
        """Convert a snapshot pair to a PyG Data object.

        Returns:
            torch_geometric.data.Data with:
            - x: node features [N, 8]
            - edge_index: [2, E]
            - edge_attr: edge features [E, 10]
            - y: labels [E] (0=normal, 1=anomalous)

        Raises:
            ImportError: If torch_geometric is not installed.
        """
        if not HAS_PYG:
            raise ImportError(
                "torch and torch_geometric are required. "
                "Install with: pip install torch torch_geometric"
            )

        node_feats = extract_node_features(current)
        node_names = list(node_feats.keys())
        node_idx = {name: i for i, name in enumerate(node_names)}

        x = np.array([node_feats[n] for n in node_names], dtype=np.float32)

        baseline_edges = {
            f"{e['source']}->{e['destination']}" for e in baseline.get("edges", [])
        }

        edges = current.get("edges", [])
        max_lat = max((e.get("p99_latency_ms", 0) for e in edges), default=1000.0) or 1.0
        src_idx, dst_idx, edge_attrs, labels = [], [], [], []

        for e in edges:
            src, dst = e["source"], e["destination"]
            if src not in node_idx or dst not in node_idx:
                continue
            edge_key = f"{src}->{dst}"
            bl = self.baselines.get(edge_key)
            is_new = edge_key not in baseline_edges

            feat = extract_edge_features(
                e, baseline=bl, is_new=is_new, max_latency=max_lat
            )
            src_idx.append(node_idx[src])
            dst_idx.append(node_idx[dst])
            edge_attrs.append(feat)
            label = 1 if self.labels.get(edge_key) == "anomalous" else 0
            labels.append(label)

        edge_index = torch.tensor([src_idx, dst_idx], dtype=torch.long)
        edge_attr = torch.tensor(
            edge_attrs if edge_attrs else np.zeros((0, 10)),
            dtype=torch.float32,
        )

        return PyGData(
            x=torch.tensor(x, dtype=torch.float32),
            edge_index=edge_index,
            edge_attr=edge_attr,
            y=torch.tensor(labels, dtype=torch.long),
        )

    def to_numpy(self, baseline: dict, current: dict) -> dict[str, np.ndarray]:
        """Convert a snapshot pair to numpy arrays (no torch required).

        Returns dict with keys: x, edge_index, edge_attr, y
        """
        node_feats = extract_node_features(current)
        node_names = list(node_feats.keys())
        node_idx = {name: i for i, name in enumerate(node_names)}

        x = np.array([node_feats[n] for n in node_names], dtype=np.float32)

        baseline_edges = {
            f"{e['source']}->{e['destination']}" for e in baseline.get("edges", [])
        }

        edges = current.get("edges", [])
        max_lat = max((e.get("p99_latency_ms", 0) for e in edges), default=1000.0) or 1.0
        src_idx, dst_idx, edge_attrs, labels = [], [], [], []

        for e in edges:
            src, dst = e["source"], e["destination"]
            if src not in node_idx or dst not in node_idx:
                continue
            edge_key = f"{src}->{dst}"
            bl = self.baselines.get(edge_key)
            is_new = edge_key not in baseline_edges

            feat = extract_edge_features(
                e, baseline=bl, is_new=is_new, max_latency=max_lat
            )
            src_idx.append(node_idx[src])
            dst_idx.append(node_idx[dst])
            edge_attrs.append(feat)
            label = 1 if self.labels.get(edge_key) == "anomalous" else 0
            labels.append(label)

        return {
            "x": x,
            "edge_index": np.array([src_idx, dst_idx], dtype=np.int64),
            "edge_attr": np.array(edge_attrs, dtype=np.float32) if edge_attrs else np.zeros((0, 10), dtype=np.float32),
            "y": np.array(labels, dtype=np.int64),
        }

    def train_test_split(
        self, test_ratio: float = 0.2
    ) -> tuple[list[dict], list[dict]]:
        """Split snapshots by time (last test_ratio fraction for test).

        Returns:
            (train_snapshots, test_snapshots)
        """
        n = len(self.snapshots)
        split = max(1, int(n * (1 - test_ratio)))
        return self.snapshots[:split], self.snapshots[split:]
