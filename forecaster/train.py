"""
train.py
========
Standard supervised training loop (regression, MSE loss) with early
stopping on validation loss. Nothing optimizer-specific (Markowitz/QAOA)
happens here - this only fits the forecaster.
"""

from __future__ import annotations
import copy

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from forecaster.config import TrainConfig, TRAIN
from forecaster.dataset import ReturnDataset, SplitBundle
from forecaster.model import ReturnForecaster


def train_forecaster(bundle: SplitBundle, cfg: TrainConfig = TRAIN):
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)

    train_ds = ReturnDataset(bundle.train, bundle.scaler, bundle.asset_to_id, bundle.feature_cols)
    val_ds = ReturnDataset(bundle.val, bundle.scaler, bundle.asset_to_id, bundle.feature_cols)

    train_loader = DataLoader(train_ds, batch_size=cfg.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=cfg.batch_size, shuffle=False)

    model = ReturnForecaster(
        n_features=len(bundle.feature_cols),
        n_assets=len(bundle.asset_to_id),
    ).to(cfg.device)

    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    loss_fn = nn.MSELoss()

    best_val = float("inf")
    best_state = None
    patience_ctr = 0
    history = {"train_loss": [], "val_loss": []}

    for epoch in range(cfg.epochs):
        model.train()
        train_losses = []
        for X, aid, y in train_loader:
            X, aid, y = X.to(cfg.device), aid.to(cfg.device), y.to(cfg.device)
            optimizer.zero_grad()
            pred = model(X, aid)
            loss = loss_fn(pred, y)
            loss.backward()
            optimizer.step()
            train_losses.append(loss.item())

        model.eval()
        val_losses = []
        with torch.no_grad():
            for X, aid, y in val_loader:
                X, aid, y = X.to(cfg.device), aid.to(cfg.device), y.to(cfg.device)
                pred = model(X, aid)
                val_losses.append(loss_fn(pred, y).item())

        train_loss = float(np.mean(train_losses))
        val_loss = float(np.mean(val_losses))
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_loss)

        if val_loss < best_val:
            best_val = val_loss
            best_state = copy.deepcopy(model.state_dict())
            patience_ctr = 0
        else:
            patience_ctr += 1

        if epoch % 10 == 0 or epoch == cfg.epochs - 1:
            print(f"epoch {epoch:3d} | train_mse {train_loss:.6f} | val_mse {val_loss:.6f}")

        if patience_ctr >= cfg.early_stopping_patience:
            print(f"Early stopping at epoch {epoch} (best val_mse={best_val:.6f})")
            break

    model.load_state_dict(best_state)
    return model, history
