
from __future__ import annotations
"""
evaluate.py
===========
Out-of-sample forecast evaluation on the TEST split only (never touched
during training or early stopping). Reports MSE/MAE and produces an
actual-vs-predicted comparison plot/table.
"""

'''from __future__ import annotations
import json

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import mean_squared_error, mean_absolute_error
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from forecaster.dataset import ReturnDataset, SplitBundle
from forecaster.model import ReturnForecaster


@torch.no_grad()
def predict_on_split(model: ReturnForecaster, df: pd.DataFrame, bundle: SplitBundle) -> pd.DataFrame:
    ds = ReturnDataset(df, bundle.scaler, bundle.asset_to_id, bundle.feature_cols)
    model.eval()
    preds = model(ds.X, ds.asset_ids).numpy()
    out = pd.DataFrame({
        "date": ds.dates,
        "asset": ds.assets,
        "actual_return": ds.y.numpy(),
        "predicted_return": preds,
    })
    return out


def evaluate_test_set(model: ReturnForecaster, bundle: SplitBundle,
                       metrics_path: str, plot_path: str) -> dict:
    result = predict_on_split(model, bundle.test, bundle)

    mse = mean_squared_error(result["actual_return"], result["predicted_return"])
    mae = mean_absolute_error(result["actual_return"], result["predicted_return"])

    # Directional accuracy is a useful secondary sanity check for a finance
    # audience: did the model at least get the sign right more than 50% of
    # the time?
    direction_hit_rate = float(
        (np.sign(result["actual_return"]) == np.sign(result["predicted_return"])).mean()
    )

    metrics = {
        "test_mse": float(mse),
        "test_mae": float(mae),
        "test_direction_hit_rate": direction_hit_rate,
        "n_test_samples": int(len(result)),
    }

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    # --- Plot: actual vs predicted for one representative asset over time ---
    sample_asset = sorted(result["asset"].unique())[0]
    sub = result[result["asset"] == sample_asset].sort_values("date")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    axes[0].plot(sub["date"], sub["actual_return"], label="actual", alpha=0.8)
    axes[0].plot(sub["date"], sub["predicted_return"], label="predicted", alpha=0.8)
    axes[0].set_title(f"Actual vs Predicted Return — {sample_asset} (test set)")
    axes[0].set_xlabel("date")
    axes[0].set_ylabel("next-period return")
    axes[0].legend()
    axes[0].tick_params(axis="x", rotation=30)

    axes[1].scatter(result["actual_return"], result["predicted_return"], s=6, alpha=0.35)
    lim = max(result["actual_return"].abs().max(), result["predicted_return"].abs().max())
    axes[1].plot([-lim, lim], [-lim, lim], color="gray", linestyle="--", linewidth=1)
    axes[1].set_title("Actual vs Predicted — all test assets")
    axes[1].set_xlabel("actual return")
    axes[1].set_ylabel("predicted return")

    fig.tight_layout()
    fig.savefig(plot_path, dpi=130)
    plt.close(fig)

    return metrics
'''
"""
evaluate.py
===========

Out-of-sample forecast evaluation on the TEST split only.

The test split is never used during training or early stopping.
This module reports:
    - MSE
    - MAE
    - Directional hit rate

It also produces an actual-vs-predicted comparison plot.
"""


import json
import os

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import mean_squared_error, mean_absolute_error

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from forecaster.dataset import ReturnDataset, SplitBundle
from forecaster.model import ReturnForecaster


@torch.no_grad()
def predict_on_split(
    model: ReturnForecaster,
    df: pd.DataFrame,
    bundle: SplitBundle,
) -> pd.DataFrame:
    """
    Generate predictions for one data split.
    """

    dataset = ReturnDataset(
        df,
        bundle.scaler,
        bundle.asset_to_id,
        bundle.feature_cols,
    )

    model.eval()

    predictions = model(
        dataset.X,
        dataset.asset_ids,
    ).numpy()

    result = pd.DataFrame({
        "date": dataset.dates,
        "asset": dataset.assets,
        "actual_return": dataset.y.numpy(),
        "predicted_return": predictions,
    })

    return result


def evaluate_test_set(
    model: ReturnForecaster,
    bundle: SplitBundle,
    metrics_path: str,
    plot_path: str,
) -> dict:
    """
    Evaluate the trained model on the held-out TEST set.

    Returns:
        Dictionary containing test-set metrics.
    """

    # ------------------------------------------------------------
    # 1. Generate test predictions
    # ------------------------------------------------------------

    result = predict_on_split(
        model,
        bundle.test,
        bundle,
    )

    # ------------------------------------------------------------
    # 2. Calculate evaluation metrics
    # ------------------------------------------------------------

    mse = mean_squared_error(
        result["actual_return"],
        result["predicted_return"],
    )

    mae = mean_absolute_error(
        result["actual_return"],
        result["predicted_return"],
    )

    # Directional accuracy:
    # Did the model correctly predict whether the return was
    # positive or negative?
    direction_hit_rate = float(
        (
            np.sign(result["actual_return"])
            == np.sign(result["predicted_return"])
        ).mean()
    )

    metrics = {
        "test_mse": float(mse),
        "test_mae": float(mae),
        "test_direction_hit_rate": direction_hit_rate,
        "n_test_samples": int(len(result)),
    }

    # ------------------------------------------------------------
    # 3. Save metrics
    # ------------------------------------------------------------

    metrics_path = os.path.abspath(metrics_path)

    metrics_directory = os.path.dirname(metrics_path)

    if metrics_directory:
        os.makedirs(metrics_directory, exist_ok=True)

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    # ------------------------------------------------------------
    # 4. Prepare representative asset for time-series plot
    # ------------------------------------------------------------

    sample_asset = sorted(
        result["asset"].unique()
    )[0]

    sub = (
        result[result["asset"] == sample_asset]
        .sort_values("date")
    )

    # ------------------------------------------------------------
    # 5. Create plots
    # ------------------------------------------------------------

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(12, 4.5),
    )

    # ---- Plot 1: actual vs predicted over time ----

    axes[0].plot(
        sub["date"],
        sub["actual_return"],
        label="actual",
        alpha=0.8,
    )

    axes[0].plot(
        sub["date"],
        sub["predicted_return"],
        label="predicted",
        alpha=0.8,
    )

    axes[0].set_title(
        f"Actual vs Predicted Return — "
        f"{sample_asset} (test set)"
    )

    axes[0].set_xlabel("date")
    axes[0].set_ylabel("next-period return")
    axes[0].legend()
    axes[0].tick_params(
        axis="x",
        rotation=30,
    )

    # ---- Plot 2: scatter plot ----

    axes[1].scatter(
        result["actual_return"],
        result["predicted_return"],
        s=6,
        alpha=0.35,
    )

    lim = max(
        result["actual_return"].abs().max(),
        result["predicted_return"].abs().max(),
    )

    axes[1].plot(
        [-lim, lim],
        [-lim, lim],
        color="gray",
        linestyle="--",
        linewidth=1,
    )

    axes[1].set_title(
        "Actual vs Predicted — all test assets"
    )

    axes[1].set_xlabel("actual return")
    axes[1].set_ylabel("predicted return")

    # ------------------------------------------------------------
    # 6. Save plot
    # ------------------------------------------------------------

    plot_path = os.path.abspath(plot_path)

    plot_directory = os.path.dirname(plot_path)

    if plot_directory:
        os.makedirs(plot_directory, exist_ok=True)

    fig.tight_layout()

    fig.savefig(
        plot_path,
        dpi=130,
        bbox_inches="tight",
    )

    plt.close(fig)

    # ------------------------------------------------------------
    # 7. Return metrics to main.py
    # ------------------------------------------------------------

    return metrics