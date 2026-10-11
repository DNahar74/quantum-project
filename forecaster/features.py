"""
features.py
============
Turns a raw price panel into a leakage-safe, model-ready feature panel.

Design choices (documented for the report):

* Everything is computed from PAST returns only. A feature at row `t` is only
  allowed to use price/return information from time <= t. The prediction
  target at row `t` is the return realised at t + horizon (the FUTURE),
  which is exactly what makes this "next-period return prediction" rather
  than an in-sample fit.
* Features are asset-agnostic (same feature set works for any ticker), which
  is what lets one shared NN generalise across assets and, later, across
  real Yahoo Finance tickers it has never seen named explicitly.
* Output is LONG format: one row per (date, asset), which is the natural
  layout for (a) pooling all assets into one training set and (b) later
  pivoting to a wide (date x asset) matrix to build the mu_hat vector.
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from forecaster.config import DataConfig, DATA


FEATURE_COLUMNS_TEMPLATE = None  # populated dynamically, see build_feature_panel


def _asset_features(returns: pd.Series, cfg: DataConfig) -> pd.DataFrame:
    """Build the feature block for a single asset's return series."""
    feats = pd.DataFrame(index=returns.index)

    # 1. Lagged raw returns r_{t-1}...r_{t-L}: short-term autocorrelation /
    #    momentum-reversal signal.
    for lag in range(1, cfg.lag_returns + 1):
        feats[f"lag_ret_{lag}"] = returns.shift(lag - 1)  # lag=1 -> r_t itself
        # NOTE: r_t (today's return, i.e. shift(0)) is legitimately "known"
        # information at the close of day t, which is when the forecast for
        # day t+1..t+horizon is made. All deeper lags use larger shifts.

    # 2. Rolling mean return (short-horizon trend) - computed on returns up
    #    to and including t, i.e. window ends at t (no look-ahead).
    for w in cfg.roll_windows:
        feats[f"roll_mean_{w}"] = returns.rolling(w).mean()

    # 3. Rolling volatility (risk regime signal).
    for w in cfg.roll_windows:
        feats[f"roll_vol_{w}"] = returns.rolling(w).std()

    # 4. Momentum: cumulative return over the largest window.
    w_mom = max(cfg.roll_windows)
    feats[f"momentum_{w_mom}"] = (1 + returns).rolling(w_mom).apply(
        lambda x: np.prod(x) - 1, raw=True
    )

    # 5. Simple z-score of the most recent return vs. its own rolling stats.
    w_z = cfg.roll_windows[-1]
    roll_mean = returns.rolling(w_z).mean()
    roll_std = returns.rolling(w_z).std().replace(0, np.nan)
    feats[f"zscore_{w_z}"] = (returns - roll_mean) / roll_std

    return feats


def build_feature_panel(prices: pd.DataFrame, cfg: DataConfig = DATA) -> pd.DataFrame:
    """
    Parameters
    ----------
    prices : wide DataFrame (date x asset) of prices.

    Returns
    -------
    panel : long DataFrame with columns:
        ['date', 'asset', <feature columns...>, 'target']
        where 'target' = forward return over cfg.horizon steps (the label).
        Rows with any NaN (from warm-up lags/windows or from the forward
        target at the very end of the sample) are dropped.
    """
    returns = prices.pct_change()  # r_t = P_t / P_{t-1} - 1 ; first row is NaN by construction

    all_assets = []
    for asset in prices.columns:
        r = returns[asset]
        feats = _asset_features(r, cfg)

        # Forward target: return realised over the NEXT `horizon` steps,
        # i.e. using price info strictly AFTER time t. This is what
        # guarantees the label is never available to the feature builder.
        fwd_price_ratio = prices[asset].shift(-cfg.horizon) / prices[asset]
        target = fwd_price_ratio - 1.0

        feats["target"] = target
        feats["asset"] = asset
        feats["date"] = prices.index
        all_assets.append(feats)

    panel = pd.concat(all_assets, axis=0, ignore_index=True)
    panel = panel.dropna().reset_index(drop=True)

    feature_cols = [c for c in panel.columns if c not in ("asset", "date", "target")]
    panel = panel[["date", "asset"] + feature_cols + ["target"]]
    return panel


def feature_columns(panel: pd.DataFrame) -> list[str]:
    return [c for c in panel.columns if c not in ("date", "asset", "target")]


def build_latest_feature_row(prices: pd.DataFrame, cfg: DataConfig = DATA) -> pd.DataFrame:
    """
    Builds ONE feature row per asset using the most recent available price
    history — i.e. "as of today, what would we feed the model to forecast
    the NEXT period's return?"

    Unlike `build_feature_panel`, this does NOT require (and cannot compute)
    a forward target for the last row, since the future hasn't happened yet.
    This is exactly the row a live/production pipeline would construct at
    the current rebalance date, and it is what `forecast.get_mu_hat` expects.
    """
    returns = prices.pct_change()

    rows = []
    for asset in prices.columns:
        r = returns[asset]
        feats = _asset_features(r, cfg)
        last_valid = feats.dropna().iloc[[-1]].copy()
        last_valid["asset"] = asset
        last_valid["date"] = last_valid.index
        rows.append(last_valid)

    latest = pd.concat(rows, axis=0, ignore_index=True)
    feature_cols = [c for c in latest.columns if c not in ("asset", "date")]
    latest = latest[["date", "asset"] + feature_cols]
    return latest


if __name__ == "__main__":
    from forecaster.synthetic_data import generate_synthetic_prices

    prices = generate_synthetic_prices()
    panel = build_feature_panel(prices)
    print(panel.head())
    print("\nPanel shape:", panel.shape)
    print("Feature columns:", feature_columns(panel))
