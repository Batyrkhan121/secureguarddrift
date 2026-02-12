"""GNN trainer with early stopping for edge anomaly detection."""

from __future__ import annotations

import logging
from typing import Any

try:
    import torch
    from torch.optim import Adam

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

logger = logging.getLogger(__name__)

DEFAULT_LR = 0.001
DEFAULT_EPOCHS = 100
DEFAULT_PATIENCE = 10


class GNNTrainer:
    """Train and evaluate DriftGNN with early stopping.

    Args:
        model: A DriftGNN instance.
        lr: Learning rate for Adam optimizer.
    """

    def __init__(self, model: Any, lr: float = DEFAULT_LR):
        if not HAS_TORCH:
            raise ImportError(
                "torch is required. Install with: pip install torch torch_geometric"
            )
        self.model = model
        self.optimizer = Adam(model.parameters(), lr=lr)
        self.criterion = torch.nn.BCELoss()
        self._best_state: dict | None = None

    def train_epoch(self, data_list: list) -> float:
        """Train one epoch over a list of PyG Data objects. Returns avg loss."""
        self.model.train()
        total_loss = 0.0
        count = 0
        for data in data_list:
            if data.y.numel() == 0:
                continue
            self.optimizer.zero_grad()
            pred = self.model(data)
            target = data.y.float()
            # Apply class weighting for imbalanced data
            pos = target.sum().item()
            neg = len(target) - pos
            if pos > 0 and neg > 0:
                weight = torch.where(target == 1, neg / pos, 1.0)
                loss = torch.nn.functional.binary_cross_entropy(
                    pred, target, weight=weight
                )
            else:
                loss = self.criterion(pred, target)
            loss.backward()
            self.optimizer.step()
            total_loss += loss.item()
            count += 1
        return total_loss / max(count, 1)

    def evaluate(self, data_list: list) -> dict[str, float]:
        """Evaluate model. Returns accuracy, precision, recall, f1, auc_roc."""
        self.model.eval()
        all_preds, all_labels = [], []
        with torch.no_grad():
            for data in data_list:
                if data.y.numel() == 0:
                    continue
                pred = self.model(data)
                all_preds.append(pred)
                all_labels.append(data.y.float())

        if not all_preds:
            return {"accuracy": 0, "precision": 0, "recall": 0, "f1": 0, "auc_roc": 0}

        preds = torch.cat(all_preds)
        labels = torch.cat(all_labels)
        binary = (preds > 0.5).float()

        tp = ((binary == 1) & (labels == 1)).sum().item()
        fp = ((binary == 1) & (labels == 0)).sum().item()
        fn = ((binary == 0) & (labels == 1)).sum().item()
        tn = ((binary == 0) & (labels == 0)).sum().item()

        accuracy = (tp + tn) / max(tp + tn + fp + fn, 1)
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-8)

        # AUC-ROC (simple trapezoidal approximation)
        try:
            sorted_indices = torch.argsort(preds, descending=True)
            sorted_labels = labels[sorted_indices]
            tpr_list, fpr_list = [0.0], [0.0]
            tp_cum, fp_cum = 0, 0
            total_pos = labels.sum().item()
            total_neg = len(labels) - total_pos
            for lbl in sorted_labels:
                if lbl == 1:
                    tp_cum += 1
                else:
                    fp_cum += 1
                tpr_list.append(tp_cum / max(total_pos, 1))
                fpr_list.append(fp_cum / max(total_neg, 1))
            auc = sum(
                (fpr_list[i] - fpr_list[i - 1]) * (tpr_list[i] + tpr_list[i - 1]) / 2
                for i in range(1, len(fpr_list))
            )
        except Exception:
            auc = 0.0

        return {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "auc_roc": round(auc, 4),
        }

    def train(
        self,
        train_data: list,
        test_data: list,
        epochs: int = DEFAULT_EPOCHS,
        patience: int = DEFAULT_PATIENCE,
    ) -> dict[str, float]:
        """Full training loop with early stopping on test loss.

        Returns best test metrics and saves model checkpoint internally.
        """
        best_loss = float("inf")
        wait = 0
        best_metrics: dict[str, float] = {}

        for epoch in range(1, epochs + 1):
            loss = self.train_epoch(train_data)
            metrics = self.evaluate(test_data)

            if loss < best_loss:
                best_loss = loss
                wait = 0
                best_metrics = metrics
                self._best_state = {
                    k: v.clone() for k, v in self.model.state_dict().items()
                }
            else:
                wait += 1

            if epoch % 10 == 0 or wait == 0:
                logger.info(
                    "Epoch %d: loss=%.4f f1=%.4f auc=%.4f",
                    epoch, loss, metrics["f1"], metrics["auc_roc"],
                )

            if wait >= patience:
                logger.info("Early stopping at epoch %d", epoch)
                break

        if self._best_state:
            self.model.load_state_dict(self._best_state)
        return best_metrics

    def save(self, path: str) -> None:
        """Save model state dict to file."""
        torch.save(self.model.state_dict(), path)
        logger.info("Model saved to %s", path)

    def load(self, path: str) -> None:
        """Load model state dict from file."""
        self.model.load_state_dict(torch.load(path, weights_only=True))
        logger.info("Model loaded from %s", path)
