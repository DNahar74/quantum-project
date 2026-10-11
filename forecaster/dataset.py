"""
dataset.py
==========
Chronological (walk-forward-safe) train/val/test splitting + scaling +
PyTorch Dataset wrapping.

Key anti-leakage rules enforced here:
1. The split is done by DATE, not by row-shuffling — every asset's train
   rows end before every asset's validation rows begin, which in turn end
   before test rows begin.
2. An `embargo` gap (in trading days) is purged around each split boundary.
   Because features use rolling windows up to `max(roll_windows)` days and
   the target looks `horizon` days forward, rows straddling a boundary can
   otherwise leak information across the split. Purging removes them.
3. Feature scaling (StandardScaler) is fit ONLY on the training split and
   then applied to val/test — never fit on data the model will be
   evaluated on.
"""

from __future__ import annotations
from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch.utils.data import Dataset

from forecaster.config import DataConfig, DATA
from forecaster.features import feature_columns


@dataclass
class SplitBundle:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame
    scaler: StandardScaler
    asset_to_id: dict
    feature_cols: list


def chronological_split(panel: pd.DataFrame, cfg: DataConfig = DATA) -> SplitBundle:
    dates = np.sort(panel["date"].unique())
    n_dates = len(dates)

    train_end = int(n_dates * cfg.train_frac)
    val_end = train_end + int(n_dates * cfg.val_frac)

    e = cfg.embargo
    train_dates = dates[: max(0, train_end - e)]
    val_dates = dates[train_end + e: max(train_end + e, val_end - e)]
    test_dates = dates[val_end + e:]

    train = panel[panel["date"].isin(train_dates)].reset_index(drop=True)
    val = panel[panel["date"].isin(val_dates)].reset_index(drop=True)
    test = panel[panel["date"].isin(test_dates)].reset_index(drop=True)

    feat_cols = feature_columns(panel)

    # Fit scaler on TRAIN ONLY.
    scaler = StandardScaler()
    scaler.fit(train[feat_cols].values)

    assets = sorted(panel["asset"].unique())
    asset_to_id = {a: i for i, a in enumerate(assets)}

    return SplitBundle(train, val, test, scaler, asset_to_id, feat_cols)


class ReturnDataset(Dataset):
    """Wraps a (long-format) split DataFrame as a PyTorch Dataset.

    Each sample = (scaled_feature_vector, asset_id, target_return).
    The asset_id lets the shared MLP learn a small per-asset embedding
    while still being ONE model with ONE set of weights (see model.py).
    """

    def __init__(self, df: pd.DataFrame, scaler: StandardScaler,
                 asset_to_id: dict, feat_cols: list):
        X = scaler.transform(df[feat_cols].values).astype(np.float32)
        self.X = torch.from_numpy(X)
        self.asset_ids = torch.tensor(
            df["asset"].map(asset_to_id).values, dtype=torch.long
        )
        self.y = torch.tensor(df["target"].values.astype(np.float32))
        self.dates = df["date"].values
        self.assets = df["asset"].values

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.asset_ids[idx], self.y[idx]


if __name__ == "__main__":
    from forecaster.synthetic_data import generate_synthetic_prices
    from forecaster.features import build_feature_panel

    prices = generate_synthetic_prices()
    panel = build_feature_panel(prices)
    bundle = chronological_split(panel)

    print("Train rows:", len(bundle.train), " date range:",
          bundle.train["date"].min(), "->", bundle.train["date"].max())
    print("Val rows:  ", len(bundle.val), " date range:",
          bundle.val["date"].min(), "->", bundle.val["date"].max())
    print("Test rows: ", len(bundle.test), " date range:",
          bundle.test["date"].min(), "->", bundle.test["date"].max())
    print("Assets:", bundle.asset_to_id)
