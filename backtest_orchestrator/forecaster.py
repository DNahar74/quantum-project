import os
from functools import lru_cache
from typing import List

import pandas as pd

DEFAULT_MU_HAT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "processed", "mu_hat.csv"
)

# mu_hat.csv holds forecasts of the return over the next 5 trading days (forecaster.config
# DataConfig.horizon). The orchestrator scales the daily Sigma by this to match.
MU_HAT_HORIZON_DAYS = 5


class MuHatUnavailableError(LookupError):
    """The mu_hat file has no forecast for the requested rebalance date."""


@lru_cache(maxsize=4)
def _read_mu_hat(path: str, mtime: float) -> pd.DataFrame:
    # Keyed on mtime so a rebuilt file is re-read; callers must not mutate the result.
    return pd.read_csv(path, index_col="date", parse_dates=["date"])


def get_mu_hat(date: str | pd.Timestamp, tickers: List[str]) -> List[float]:
    """
    Looks up the forecaster's expected returns for a rebalance date.

    Values come from MU_HAT_FILE, defaulting to data/processed/mu_hat.csv, which
    `python -m forecaster.build_mu_hat` writes. Each value is a forecast of the
    asset's return over the next MU_HAT_HORIZON_DAYS trading days.

    Args:
        date: The rebalance date.
        tickers: Assets in the order the request lists them.

    Returns:
        One expected return per ticker, in the given order.

    Raises:
        MuHatUnavailableError: If the file has no row for the date.
        ValueError: If the file is missing a ticker or holds a NaN for the date.
    """
    path = os.environ.get("MU_HAT_FILE", DEFAULT_MU_HAT_FILE)
    table = _read_mu_hat(path, os.path.getmtime(path))

    date = pd.to_datetime(date)
    if date not in table.index:
        raise MuHatUnavailableError(f"No mu_hat for {date.date()} in {path}")

    missing = [t for t in tickers if t not in table.columns]
    if missing:
        raise ValueError(f"mu_hat file {path} has no column for {missing}; rebuild it for this asset list")

    row = table.loc[date, tickers]
    if row.isna().any():
        raise ValueError(f"mu_hat for {date.date()} has NaN for {list(row[row.isna()].index)}")
    return [float(v) for v in row]
