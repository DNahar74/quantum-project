"""
build_mu_hat.py
===============
Offline walk-forward run that writes the mu_hat file the backtest reads:

    daily_returns.csv -> price index
    -> for each yearly retrain date R: train on prices up to R, then predict
       mu_hat for every rebalance Friday from R until the next retrain
    -> mu_hat.csv (one row per rebalance Friday, one column per asset)

Each prediction uses only prices up to its own Friday, and each model only
sees targets that were realised by its retrain date, so no row of the file
depends on anything after its date (tests/test_forecaster.py checks this).

Run from the repo root, after the data loader:
    python -m forecaster.build_mu_hat

RETURNS_FILE and MU_HAT_FILE override the default input and output paths.
Nothing here downloads data.
"""

from __future__ import annotations
import logging
import os
from dataclasses import replace

import pandas as pd

from forecaster.config import (DataConfig, TrainConfig, WalkForwardConfig,
                               DATA, TRAIN, WALK_FORWARD)
from forecaster.dataset import chronological_split
from forecaster.features import build_feature_panel, build_latest_feature_row
from forecaster.forecast import get_mu_hat
from forecaster.train import train_forecaster

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RETURNS_FILE = os.path.join(ROOT_DIR, "data", "processed", "daily_returns.csv")
DEFAULT_MU_HAT_FILE = os.path.join(ROOT_DIR, "data", "processed", "mu_hat.csv")

logger = logging.getLogger("forecaster.build_mu_hat")


def load_price_index(returns_file: str) -> pd.DataFrame:
    """Reads the data loader's daily returns and compounds them into the price index features.py expects."""
    returns = pd.read_csv(returns_file, index_col="date", parse_dates=["date"])
    return (1.0 + returns).cumprod()


def rebalance_fridays(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Same rule as the orchestrator: every Friday that is a trading day in the returns file."""
    return index[index.dayofweek == 4]


def retrain_dates(index: pd.DatetimeIndex, min_train_years: int) -> list[pd.Timestamp]:
    """First rebalance Friday of each calendar year, once `min_train_years` of history exist."""
    fridays = rebalance_fridays(index)
    eligible = fridays[fridays >= index[0] + pd.DateOffset(years=min_train_years)]
    return list(eligible.to_series().groupby(eligible.year).min())


def features_as_of(prices: pd.DataFrame, date: pd.Timestamp, cfg: DataConfig) -> pd.DataFrame | None:
    """
    One feature row per asset for `date`, built from prices up to and including
    `date` only. Returns None if any asset has no valid row on that exact date
    (e.g. a zero-variance window), rather than silently using an older row.
    """
    # Features look back at most max(lag, window) returns; keep a margin.
    lookback = 2 * (max(cfg.lag_returns, max(cfg.roll_windows)) + 1)
    try:
        rows = build_latest_feature_row(prices.loc[:date].tail(lookback), cfg)
    except IndexError:
        return None
    if (rows["date"] != date).any():
        return None
    return rows


def build_mu_hat(prices: pd.DataFrame, data_cfg: DataConfig = DATA, train_cfg: TrainConfig = TRAIN,
                 wf_cfg: WalkForwardConfig = WALK_FORWARD) -> pd.DataFrame:
    """
    Walk-forward mu_hat for every rebalance Friday from the first retrain date on.

    Returns a DataFrame indexed by date, one column per asset in `prices`
    column order, values = predicted `data_cfg.horizon`-day return.
    """
    fridays = rebalance_fridays(prices.index)
    retrains = retrain_dates(prices.index, wf_cfg.min_train_years)
    if not retrains:
        raise ValueError(f"Need at least {wf_cfg.min_train_years} years of prices before the first retrain.")

    # The tail of each training window is the early-stopping set; no test split is needed here.
    split_cfg = replace(data_cfg, train_frac=1.0 - wf_cfg.val_frac, val_frac=wf_cfg.val_frac)

    rows: dict[pd.Timestamp, pd.Series] = {}
    for k, retrain_date in enumerate(retrains):
        next_retrain = retrains[k + 1] if k + 1 < len(retrains) else None

        # Only prices known at the retrain date's close. build_feature_panel drops
        # rows whose forward target would end after it.
        panel = build_feature_panel(prices.loc[:retrain_date], data_cfg)
        bundle = chronological_split(panel, split_cfg)
        model, _ = train_forecaster(bundle, train_cfg)

        period = fridays[fridays >= retrain_date]
        if next_retrain is not None:
            period = period[period < next_retrain]
        for friday in period:
            latest = features_as_of(prices, friday, data_cfg)
            if latest is None:
                logger.warning("No complete feature row on %s; leaving it out of mu_hat", friday.date())
                continue
            rows[friday] = get_mu_hat(model, latest, bundle)

        logger.info("Retrain %d/%d on %s: %d train / %d val rows, %d Fridays predicted",
                    k + 1, len(retrains), retrain_date.date(), len(bundle.train), len(bundle.val), len(period))

    table = pd.DataFrame.from_dict(rows, orient="index")[list(prices.columns)]
    table.index.name = "date"
    return table


def main() -> None:
    """Builds the mu_hat file; RETURNS_FILE and MU_HAT_FILE override the defaults."""
    logging.basicConfig(level=logging.INFO)
    returns_file = os.environ.get("RETURNS_FILE", DEFAULT_RETURNS_FILE)
    out_file = os.environ.get("MU_HAT_FILE", DEFAULT_MU_HAT_FILE)

    table = build_mu_hat(load_price_index(returns_file))

    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    table.to_csv(out_file)
    logger.info("Wrote mu_hat for %d rebalance dates (%s to %s), %d assets, to %s",
                len(table), table.index.min().date(), table.index.max().date(), len(table.columns), out_file)


if __name__ == "__main__":
    main()
