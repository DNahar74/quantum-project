"""
model.py
========
A deliberately simple feed-forward network (MLP), not an LSTM/Transformer.

Justification (for the report):
- The input is already a hand-built set of time-series features (lagged
  returns, rolling mean/vol, momentum, z-score) rather than a raw sequence,
  so a recurrent/attention model gains little here and adds a lot of
  training complexity, hyperparameters and overfitting risk for a
  final-year-project-sized dataset.
- A small MLP is easy to justify, easy to reproduce, trains in seconds,
  and is a very standard choice in the return-prediction literature when
  features are pre-engineered.
- One shared MLP (with a small learned per-asset embedding concatenated to
  the features) is trained on POOLED data across all assets. This directly
  satisfies the project requirement of "one common forecaster" whose
  output is optimizer-agnostic, and it lets the same trained model later
  score assets it has never explicitly memorised return statistics for.
"""

from __future__ import annotations
import torch
import torch.nn as nn

from forecaster.config import ModelConfig, MODEL


class ReturnForecaster(nn.Module):
    def __init__(self, n_features: int, n_assets: int, cfg: ModelConfig = MODEL):
        super().__init__()
        self.asset_embedding = nn.Embedding(n_assets, cfg.asset_embedding_dim)

        act = {"relu": nn.ReLU, "gelu": nn.GELU, "tanh": nn.Tanh}[cfg.activation]

        dims = [n_features + cfg.asset_embedding_dim] + list(cfg.hidden_dims)
        layers = []
        for i in range(len(dims) - 1):
            layers += [
                nn.Linear(dims[i], dims[i + 1]),
                act(),
                nn.Dropout(cfg.dropout),
            ]
        layers.append(nn.Linear(dims[-1], 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor, asset_id: torch.Tensor) -> torch.Tensor:
        emb = self.asset_embedding(asset_id)
        h = torch.cat([x, emb], dim=-1)
        out = self.net(h)
        return out.squeeze(-1)  # (batch,) predicted next-period return
