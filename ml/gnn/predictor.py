"""Production inference for GNN-based edge anomaly detection."""

from __future__ import annotations

import logging
import os
from typing import Any

from ml.gnn.dataset import DriftDataset
from ml.gnn.model import HAS_TORCH

if HAS_TORCH:
    import torch

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = "data/gnn_model.pt"
DEFAULT_THRESHOLD = 0.7


class GNNPredictor:
    """Load trained GNN model and predict anomaly scores per edge.

    Graceful fallback: if model file doesn't exist or torch is not
    installed, all predict methods return empty results.
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model: Any = None
        self._available = False

        if not HAS_TORCH:
            logger.warning("torch not installed — GNN predictions disabled")
            return

        from ml.gnn.model import DriftGNN

        self.model = DriftGNN()
        if os.path.exists(model_path):
            self.model.load_state_dict(
                torch.load(model_path, weights_only=True)
            )
            self._available = True
            logger.info("GNN model loaded from %s", model_path)
        else:
            logger.warning(
                "Model file %s not found — predictions will be empty",
                model_path,
            )
        self.model.eval()

    @property
    def available(self) -> bool:
        """Whether the model is ready for predictions."""
        return self._available

    def predict(
        self,
        baseline: dict,
        current: dict,
        baselines: dict[str, dict] | None = None,
    ) -> dict[str, float]:
        """Predict anomaly score for each edge.

        Args:
            baseline: Baseline snapshot dict.
            current: Current snapshot dict.
            baselines: Optional per-edge baseline stats.

        Returns:
            Mapping of edge key ("source->destination") to anomaly
            probability in [0, 1]. Empty dict if model not available.
        """
        if not self._available:
            return {}

        ds = DriftDataset([], baselines=baselines)
        data = ds.to_pyg(baseline, current)

        if data.edge_index.numel() == 0:
            return {}

        with torch.no_grad():
            scores = self.model(data)
        edges = current.get("edges", [])
        result: dict[str, float] = {}
        for i, edge in enumerate(edges):
            src, dst = edge["source"], edge["destination"]
            key = f"{src}->{dst}"
            if i < len(scores):
                result[key] = round(scores[i].item(), 4)
        return result

    def get_top_anomalies(
        self,
        baseline: dict,
        current: dict,
        threshold: float = DEFAULT_THRESHOLD,
        baselines: dict[str, dict] | None = None,
    ) -> list[dict]:
        """Return edges with anomaly score above threshold.

        Args:
            baseline: Baseline snapshot dict.
            current: Current snapshot dict.
            threshold: Minimum anomaly score to include.
            baselines: Optional per-edge baseline stats.

        Returns:
            List of dicts with edge_key, score, source, destination.
            Sorted by score descending.
        """
        scores = self.predict(baseline, current, baselines=baselines)
        anomalies = []
        for key, score in scores.items():
            if score >= threshold:
                src, dst = key.split("->", 1)
                anomalies.append({
                    "edge_key": key,
                    "source": src,
                    "destination": dst,
                    "score": score,
                })
        anomalies.sort(key=lambda x: x["score"], reverse=True)
        return anomalies
