"""
synthetic_data.py
==================
Generates synthetic multi-asset daily price data from a KNOWN
return-generating process, so that forecaster quality can be checked
against ground truth before ever touching real (Yahoo Finance) data.

Return-generating process (per asset i, day t):

    r_i,t = mu_i                              (asset drift)
          + beta_i * f_t                      (exposure to a common market factor)
          + phi_i * r_i,t-1                   (weak AR(1) momentum term - this is
                                                 the exploitable signal the NN should
                                                 learn to partially recover)
          + eps_i,t                           (idiosyncratic noise)

    f_t  ~ N(0, factor_vol^2)                 (common market factor, shared by all assets)
    eps_i,t ~ N(0, idio_vol_i^2)

Prices are then P_i,t = P_i,0 * exp(cumsum(r_i,:t)).

This file has NO dependency on the model or the optimizers - it only
produces a price panel (DataFrame: index=date, columns=tickers).
"""

from __future__ import annotations
import numpy as np
import pandas as pd

from forecaster.config import DataConfig, DATA


def generate_synthetic_prices(cfg: DataConfig = DATA) -> pd.DataFrame:
    """
    Returns
    -------
    prices : pd.DataFrame
        shape (n_periods+1, n_assets), index = integer/date-like RangeIndex,
        columns = synthetic tickers "AST_00", "AST_01", ...
    """
    rng = np.random.default_rng(cfg.seed)

    n, T = cfg.n_assets, cfg.n_periods
    tickers = [f"AST_{i:02d}" for i in range(n)]

    mu = rng.uniform(*cfg.mean_return_range, size=n)
    beta = rng.uniform(0.3, 1.2, size=n)
    phi = rng.uniform(*cfg.ar_coefficient_range, size=n)
    idio_vol = rng.uniform(*cfg.idio_vol_range, size=n)

    factor = rng.normal(0, cfg.factor_vol, size=T)

    returns = np.zeros((T, n))
    prev_r = np.zeros(n)
    for t in range(T):
        eps = rng.normal(0, idio_vol, size=n)
        r_t = mu + beta * factor[t] + phi * prev_r + eps
        returns[t] = r_t
        prev_r = r_t

    log_prices = np.cumsum(returns, axis=0)
    prices = 100.0 * np.exp(log_prices)  # start every asset at price 100

    # prepend day-0 starting price row so pct_change() later has n_periods
    # usable return observations
    prices = np.vstack([np.full((1, n), 100.0), prices])

    dates = pd.date_range("2015-01-01", periods=T + 1, freq="B")
    df = pd.DataFrame(prices, index=dates, columns=tickers)

    # stash ground truth for optional diagnostic use (not used by the NN)
    df.attrs["ground_truth"] = {
        "mu": dict(zip(tickers, mu)),
        "beta": dict(zip(tickers, beta)),
        "phi": dict(zip(tickers, phi)),
        "idio_vol": dict(zip(tickers, idio_vol)),
    }
    return df


if __name__ == "__main__":
    prices = generate_synthetic_prices()
    print(prices.head())
    print("\nShape:", prices.shape)
    print("\nGround-truth per-asset drift (mu):")
    for k, v in prices.attrs["ground_truth"]["mu"].items():
        print(f"  {k}: {v:.5f}")
