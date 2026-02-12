"""GraphSAGE-based edge anomaly detector for service graph drift."""

from __future__ import annotations

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.nn import SAGEConv

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# Architecture constants
NODE_FEATURES = 8
EDGE_FEATURES = 10
HIDDEN_DIM = 32
EMBED_DIM = HIDDEN_DIM // 2  # 16
EDGE_INPUT_DIM = EMBED_DIM * 2 + EDGE_FEATURES  # 42
DROPOUT = 0.3


def _require_torch() -> None:
    if not HAS_TORCH:
        raise ImportError(
            "torch and torch_geometric are required. "
            "Install with: pip install torch torch_geometric"
        )


def create_model(
    node_features: int = NODE_FEATURES,
    edge_features: int = EDGE_FEATURES,
    hidden: int = HIDDEN_DIM,
) -> "DriftGNN":
    """Factory to create a DriftGNN model instance."""
    _require_torch()
    return DriftGNN(node_features, edge_features, hidden)


if HAS_TORCH:

    class DriftGNN(nn.Module):
        """GraphSAGE-based edge anomaly detector.

        Architecture:
        1. Node embedding: 2x SAGEConv layers (8 → 32 → 16)
        2. Edge embedding: concat(src, dst, edge_feat) → 42-dim
        3. Edge classifier: Linear(42→16) → ReLU → Linear(16→1) → Sigmoid

        Output: anomaly probability per edge [0, 1]
        Total parameters: ~6K (lightweight, < 100K limit)
        """

        def __init__(
            self,
            node_features: int = NODE_FEATURES,
            edge_features: int = EDGE_FEATURES,
            hidden: int = HIDDEN_DIM,
        ):
            super().__init__()
            embed_dim = hidden // 2

            self.conv1 = SAGEConv(node_features, hidden)
            self.conv2 = SAGEConv(hidden, embed_dim)

            edge_input = embed_dim * 2 + edge_features
            self.edge_fc1 = nn.Linear(edge_input, embed_dim)
            self.edge_fc2 = nn.Linear(embed_dim, 1)

        def forward(self, data) -> torch.Tensor:
            """Compute anomaly scores for each edge.

            Args:
                data: PyG Data with x, edge_index, edge_attr.

            Returns:
                Tensor of anomaly probabilities per edge, shape [E].
            """
            x = F.relu(self.conv1(data.x, data.edge_index))
            x = F.dropout(x, p=DROPOUT, training=self.training)
            x = self.conv2(x, data.edge_index)

            src, dst = data.edge_index
            edge_emb = torch.cat([x[src], x[dst], data.edge_attr], dim=1)

            edge_emb = F.relu(self.edge_fc1(edge_emb))
            return torch.sigmoid(self.edge_fc2(edge_emb)).squeeze(-1)

else:

    class DriftGNN:  # type: ignore[no-redef]
        """Placeholder when torch is not installed."""

        def __init__(self, *args, **kwargs):
            _require_torch()
