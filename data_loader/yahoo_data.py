

from __future__ import annotations

import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------
# The 8 Indian stocks used in the real-data experiment
# ---------------------------------------------------------------------

INDIAN_TICKERS = [
    "RELIANCE.NS",    # Reliance Industries
    "TCS.NS",         # Tata Consultancy Services
    "INFY.NS",        # Infosys
    "HDFCBANK.NS",    # HDFC Bank
    "ICICIBANK.NS",   # ICICI Bank
    "SBIN.NS",        # State Bank of India
    "ITC.NS",         # ITC
    "LT.NS",          # Larsen & Toubro
]


def fetch_price_panel(
    tickers: list[str] = INDIAN_TICKERS,
    start: str = "2015-01-01",
    end: str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Download historical adjusted closing prices from Yahoo Finance.

    Parameters
    ----------
    tickers : list[str]
        Yahoo Finance ticker symbols.

    start : str
        First date to download, e.g. "2015-01-01".

    end : str or None
        Last date (exclusive). None means up to the latest available data.

    interval : str
        Data frequency. "1d" is used for this project.

    Returns
    -------
    pd.DataFrame
        Wide price panel:

            index   = trading dates
            columns = ticker symbols
            values  = adjusted closing prices
    """

    print("\nDownloading data from Yahoo Finance...")
    print("Tickers:", ", ".join(tickers))
    print(f"Period: {start} -> {end or 'latest'}")

    raw = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,
        progress=False,
        group_by="column",
    )

    if raw.empty:
        raise RuntimeError(
            "Yahoo Finance returned no data. "
            "Check your internet connection, ticker symbols, "
            "and requested date range."
        )

    # ---------------------------------------------------------------
    # yfinance normally returns a MultiIndex for multiple tickers:
    #
    # Price       Close
    # Ticker      INFY.NS  ITC.NS ...
    #
    # We only need the adjusted Close prices.
    # ---------------------------------------------------------------

    if isinstance(raw.columns, pd.MultiIndex):

        # Depending on the yfinance version, the levels may be
        # arranged as:
        #
        #   Price -> Ticker
        #
        # or:
        #
        #   Ticker -> Price
        #
        # Handle both safely.

        if "Close" in raw.columns.get_level_values(0):
            prices = raw["Close"].copy()

        elif "Close" in raw.columns.get_level_values(1):
            prices = raw.xs("Close", axis=1, level=1).copy()

        else:
            raise RuntimeError(
                "Could not find the Close price column in Yahoo Finance data."
            )

    else:
        # Single ticker case
        if "Close" not in raw.columns:
            raise RuntimeError(
                "Yahoo Finance data does not contain a Close column."
            )

        prices = raw[["Close"]].copy()
        prices.columns = [tickers[0]]

    # ---------------------------------------------------------------
    # Keep only the requested tickers and preserve their order.
    # ---------------------------------------------------------------

    available_tickers = [
        ticker for ticker in tickers if ticker in prices.columns
    ]

    missing_tickers = [
        ticker for ticker in tickers if ticker not in prices.columns
    ]

    if missing_tickers:
        raise RuntimeError(
            "Yahoo Finance did not return data for: "
            + ", ".join(missing_tickers)
        )

    prices = prices[available_tickers]

    # ---------------------------------------------------------------
    # Clean the price panel.
    # ---------------------------------------------------------------

    prices = prices.sort_index()

    # Remove rows where all assets are missing.
    prices = prices.dropna(how="all")

    # Fill occasional missing observations caused by data gaps.
    prices = prices.ffill()

    # Remove any remaining rows with missing values.
    prices = prices.dropna()

    # Make sure the index is a proper DatetimeIndex.
    prices.index = pd.to_datetime(prices.index)

    if len(prices) == 0:
        raise RuntimeError("No usable price observations remain after cleaning.")

    # ---------------------------------------------------------------
    # Sanity checks
    # ---------------------------------------------------------------

    if prices.isnull().any().any():
        raise RuntimeError("Price panel still contains NaN values.")

    if (prices <= 0).any().any():
        raise RuntimeError("Price panel contains non-positive prices.")

    print("\nYahoo Finance download successful.")
    print(f"Price panel shape: {prices.shape}")
    print(
        f"Date range: {prices.index.min().date()} "
        f"-> {prices.index.max().date()}"
    )

    print("\nAssets:")
    for ticker in prices.columns:
        print(
            f"  {ticker:12s} | "
            f"{len(prices[ticker]):5d} observations | "
            f"last price = {prices[ticker].iloc[-1]:.2f}"
        )

    return prices


if __name__ == "__main__":

    prices = fetch_price_panel()

    print("\nLast 5 observations:")
    print(prices.tail())