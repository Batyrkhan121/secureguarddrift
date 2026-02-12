"""Tests for GNN model, trainer, and predictor.

These tests verify structure and logic without requiring torch/torch_geometric.
When torch is not installed, tests verify graceful fallback behavior.
"""

import os
import unittest

from ml.gnn.model import HAS_TORCH, DriftGNN, create_model
from ml.gnn.model import (
    NODE_FEATURES,
    EDGE_FEATURES,
    HIDDEN_DIM,
    EMBED_DIM,
    EDGE_INPUT_DIM,
    DROPOUT,
)


class TestModelConstants(unittest.TestCase):
    """Test architecture constants are correct."""

    def test_node_features(self):
        self.assertEqual(NODE_FEATURES, 8)

    def test_edge_features(self):
        self.assertEqual(EDGE_FEATURES, 10)

    def test_hidden_dim(self):
        self.assertEqual(HIDDEN_DIM, 32)

    def test_embed_dim(self):
        self.assertEqual(EMBED_DIM, 16)

    def test_edge_input_dim(self):
        # 16 (src embed) + 16 (dst embed) + 10 (edge features) = 42
        self.assertEqual(EDGE_INPUT_DIM, 42)

    def test_dropout(self):
        self.assertAlmostEqual(DROPOUT, 0.3)


class TestModelCreation(unittest.TestCase):
    """Test model creation and fallback."""

    def test_has_torch_flag(self):
        self.assertIsInstance(HAS_TORCH, bool)

    @unittest.skipIf(HAS_TORCH, "Only test fallback when torch not available")
    def test_no_torch_raises(self):
        with self.assertRaises(ImportError):
            DriftGNN()

    @unittest.skipIf(HAS_TORCH, "Only test fallback when torch not available")
    def test_create_model_no_torch(self):
        with self.assertRaises(ImportError):
            create_model()

    @unittest.skipIf(not HAS_TORCH, "torch required")
    def test_create_model_with_torch(self):
        model = create_model()
        self.assertIsNotNone(model)

    @unittest.skipIf(not HAS_TORCH, "torch required")
    def test_parameter_count_under_100k(self):
        model = create_model()
        total_params = sum(p.numel() for p in model.parameters())
        self.assertLess(total_params, 100_000)


class TestTrainerImport(unittest.TestCase):
    """Test trainer import and fallback."""

    @unittest.skipIf(HAS_TORCH, "Only test fallback when torch not available")
    def test_trainer_no_torch(self):
        from ml.gnn.trainer import GNNTrainer
        with self.assertRaises(ImportError):
            GNNTrainer(model=None)

    def test_trainer_defaults(self):
        from ml.gnn.trainer import DEFAULT_LR, DEFAULT_EPOCHS, DEFAULT_PATIENCE
        self.assertEqual(DEFAULT_LR, 0.001)
        self.assertEqual(DEFAULT_EPOCHS, 100)
        self.assertEqual(DEFAULT_PATIENCE, 10)


class TestPredictorFallback(unittest.TestCase):
    """Test predictor graceful fallback when model not available."""

    def test_predictor_no_model_file(self):
        from ml.gnn.predictor import GNNPredictor
        pred = GNNPredictor(model_path="/nonexistent/model.pt")
        self.assertFalse(pred.available)

    def test_predict_returns_empty_when_unavailable(self):
        from ml.gnn.predictor import GNNPredictor
        pred = GNNPredictor(model_path="/nonexistent/model.pt")
        result = pred.predict(
            baseline={"nodes": [], "edges": []},
            current={"nodes": [], "edges": []},
        )
        self.assertEqual(result, {})

    def test_get_top_anomalies_returns_empty(self):
        from ml.gnn.predictor import GNNPredictor
        pred = GNNPredictor(model_path="/nonexistent/model.pt")
        result = pred.get_top_anomalies(
            baseline={"nodes": [], "edges": []},
            current={"nodes": [], "edges": []},
        )
        self.assertEqual(result, [])

    def test_predictor_available_property(self):
        from ml.gnn.predictor import GNNPredictor
        pred = GNNPredictor(model_path="/nonexistent/model.pt")
        self.assertIsInstance(pred.available, bool)

    def test_predictor_defaults(self):
        from ml.gnn.predictor import DEFAULT_MODEL_PATH, DEFAULT_THRESHOLD
        self.assertEqual(DEFAULT_MODEL_PATH, "data/gnn_model.pt")
        self.assertAlmostEqual(DEFAULT_THRESHOLD, 0.7)


@unittest.skipIf(not HAS_TORCH, "torch + torch_geometric required")
class TestModelForward(unittest.TestCase):
    """Integration tests requiring torch."""

    def test_forward_pass(self):
        import torch
        from torch_geometric.data import Data

        model = create_model()
        model.eval()
        data = Data(
            x=torch.randn(4, 8),
            edge_index=torch.tensor([[0, 1, 2], [1, 2, 3]]),
            edge_attr=torch.randn(3, 10),
        )
        with torch.no_grad():
            scores = model(data)
        self.assertEqual(scores.shape, (3,))
        for s in scores:
            self.assertGreaterEqual(s.item(), 0.0)
            self.assertLessEqual(s.item(), 1.0)

    def test_inference_time(self):
        import time
        import torch
        from torch_geometric.data import Data

        model = create_model()
        model.eval()
        # 50 nodes, 100 edges — should be < 100ms
        data = Data(
            x=torch.randn(50, 8),
            edge_index=torch.randint(0, 50, (2, 100)),
            edge_attr=torch.randn(100, 10),
        )
        start = time.time()
        with torch.no_grad():
            model(data)
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.1)  # < 100ms


if __name__ == "__main__":
    unittest.main()
