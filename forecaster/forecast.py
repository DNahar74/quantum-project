"""
forecast.py
===========
THE INTERFACE FILE.

This module defines the exact, frozen contract between the NN forecaster
and whatever consumes it next (Markowitz QP, QAOA QUBO builder, etc.).

Everything upstream (synthetic_data / features / dataset / model / train)
is an implementation detail. Downstream modules should only ever need to
import from HERE.

Contract
--------
`get_mu_hat(model, panel_row_for_each_asset, bundle) -> pd.Series`
    A pandas Series indexed by ticker, one predicted next-period return per
    asset, i.e. exactly:
        mu_hat = [mu_hat_1, mu_hat_2, ..., mu_hat_n]
    This is the ONE vector both Markowitz and QAOA must receive unchanged.
    Covariance estimation (Sigma) is explicitly OUT OF SCOPE of this module
    - the optimizer modules are expected to estimate Sigma themselves
    (e.g. sample covariance of historical returns), per the project's own
    pipeline diagram.

`export_mu_hat(mu_hat, csv_path, json_path)`
    Persists mu_hat to disk in two plain, dependency-free formats so that a
    completely separate Markowitz script or QAOA/QUBO script can load it
    with nothing more than pandas or the standard json module - no need to
    import any of this forecaster's code or its PyTorch model.
"""

from __future__ import annotations
import json
from dataclasses import asdict

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler

from forecaster.config import ModelConfig
from forecaster.dataset import SplitBundle, ReturnDataset
from forecaster.model import ReturnForecaster


@torch.no_grad()
def get_mu_hat(model: ReturnForecaster, latest_rows: pd.DataFrame,
                bundle: SplitBundle) -> pd.Series:
    """
    Parameters
    ----------
    model : trained ReturnForecaster
    latest_rows : DataFrame with exactly ONE row per asset - the most
        recent feature row available for each asset (i.e. the row you'd
        use to forecast the NEXT period from "today"). Must contain the
        same feature columns as training data plus an 'asset' column.
    bundle : the SplitBundle used at training time (supplies the fitted
        scaler and asset_to_id mapping, so scaling is applied identically).

    Returns
    -------
    mu_hat : pd.Series
        index = asset ticker (sorted), values = predicted next-period
        return. This is the sole object handed to Markowitz and QAOA.
    """
    assert latest_rows["asset"].is_unique, (
        "get_mu_hat expects exactly one (the most recent) row per asset"
    )

    ds = ReturnDataset(
        latest_rows.assign(target=0.0),  # target unused at inference time
        bundle.scaler, bundle.asset_to_id, bundle.feature_cols,
    )
    model.eval()
    preds = model(ds.X, ds.asset_ids).numpy()

    mu_hat = pd.Series(preds, index=latest_rows["asset"].values, name="mu_hat")
    return mu_hat.sort_index()


def export_mu_hat(mu_hat: pd.Series, csv_path: str, json_path: str) -> None:
    """Writes mu_hat in two portable, framework-agnostic formats."""
    df = mu_hat.rename_axis("asset").reset_index(name="mu_hat")
    df.to_csv(csv_path, index=False)

    with open(json_path, "w") as f:
        json.dump(mu_hat.to_dict(), f, indent=2)


def load_mu_hat(json_path: str) -> pd.Series:
    """
    Convenience loader for the Markowitz / QAOA side. Deliberately does
    NOT import torch or anything from this package - a downstream module
    can copy just this function if it wants zero dependency on the
    forecaster's internals.
    """
    with open(json_path) as f:
        data = json.load(f)
    return pd.Series(data, name="mu_hat").sort_index()


def save_forecaster(model: ReturnForecaster, bundle: SplitBundle, path: str,
                    model_cfg: ModelConfig) -> None:
    """
    Saves everything needed to score new rows later: the weights, the model
    architecture, the asset map, the feature names and the FITTED scaler.
    Without the scaler a reloaded model would see unscaled features.
    """
    torch.save(
        {
            "state_dict": model.state_dict(),
            "model_cfg": asdict(model_cfg),
            "asset_to_id": bundle.asset_to_id,
            "feature_cols": bundle.feature_cols,
            "scaler_mean": bundle.scaler.mean_.tolist(),
            "scaler_scale": bundle.scaler.scale_.tolist(),
        },
        path,
    )


def load_forecaster(path: str) -> tuple[ReturnForecaster, SplitBundle]:
    """
    Inverse of `save_forecaster`. Returns the model and a SplitBundle that
    carries only the inference state (scaler, asset map, feature names), so
    it can be passed straight to `get_mu_hat`.
    """
    ckpt = torch.load(path, weights_only=True)

    scaler = StandardScaler()
    scaler.mean_ = np.asarray(ckpt["scaler_mean"], dtype=float)
    scaler.scale_ = np.asarray(ckpt["scaler_scale"], dtype=float)
    scaler.var_ = scaler.scale_ ** 2
    scaler.n_features_in_ = len(scaler.mean_)

    model = ReturnForecaster(
        n_features=len(ckpt["feature_cols"]),
        n_assets=len(ckpt["asset_to_id"]),
        cfg=ModelConfig(**ckpt["model_cfg"]),
    )
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    empty = pd.DataFrame()
    bundle = SplitBundle(empty, empty, empty, scaler, ckpt["asset_to_id"], ckpt["feature_cols"])
    return model, bundle
