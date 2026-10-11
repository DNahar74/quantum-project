"""
config.py
=========
Single source of truth for every hyperparameter / setting used across the
forecaster pipeline. Nothing about Markowitz or QAOA lives here - this file
only configures the NN Return Forecaster module.

Change values here (not inside individual scripts) when you swap synthetic
data for real Yahoo Finance data later.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class DataConfig:
    # --- Synthetic data generation ---
    n_assets: int = 8
    n_periods: int = 5000          # number of daily time steps to simulate
    seed: int = 42

    # Ground-truth synthetic return-generating process (used ONLY to
    # generate synthetic prices; the NN never sees these parameters).
    factor_vol: float = 0.01       # daily vol of the common market factor
    idio_vol_range: tuple = (0.005, 0.02)   # per-asset idiosyncratic vol
    mean_return_range: tuple = (-0.0002, 0.0006)  # per-asset drift
    ar_coefficient_range: tuple = (0.02, 0.12)     # weak momentum signal
                                                    # the NN is meant to learn

    # --- Feature engineering ---
    lag_returns: int = 10          # number of lagged daily returns as features
    roll_windows: List[int] = field(default_factory=lambda: [5, 10, 20])
    horizon: int = 5               # predict the return over the next H trading days (one week)

    # --- Train / val / test split (chronological, NOT shuffled) ---
    train_frac: float = 0.70
    val_frac: float = 0.15
    test_frac: float = 0.15        # (kept for documentation; inferred as remainder)
    embargo: int = 25              # gap (in time steps) purged between splits;
                                    # covers max(roll_windows)=20 plus horizon=5
                                    # to avoid leakage through rolling windows


@dataclass
class ModelConfig:
    hidden_dims: List[int] = field(default_factory=lambda: [64, 32])
    dropout: float = 0.10
    asset_embedding_dim: int = 4   # small learned embedding per asset id
    activation: str = "relu"


@dataclass
class TrainConfig:
    epochs: int = 200
    batch_size: int = 256
    lr: float = 1e-3
    weight_decay: float = 1e-5
    early_stopping_patience: int = 15
    device: str = "cpu"
    seed: int = 42


@dataclass
class WalkForwardConfig:
    # build_mu_hat.py retrains once a year, on the first rebalance Friday of
    # each calendar year, on everything known at that date's close.
    min_train_years: int = 5       # history required before the first retrain;
                                    # Fridays before it get no mu_hat
    val_frac: float = 0.15         # tail of each training window used for early stopping


@dataclass
class PathConfig:
    output_dir: str = "outputs"
    model_path: str = "outputs/forecaster.pt"
    mu_hat_csv: str = "outputs/mu_hat.csv"
    mu_hat_json: str = "outputs/mu_hat.json"
    eval_plot: str = "outputs/actual_vs_predicted.png"
    metrics_json: str = "outputs/metrics.json"


DATA = DataConfig()
MODEL = ModelConfig()
TRAIN = TrainConfig()
WALK_FORWARD = WalkForwardConfig()
PATHS = PathConfig()
