import os
import pandas as pd
from sklearn.covariance import LedoitWolf

def sigma_for_date(date: str | pd.Timestamp, window_days: int = 252) -> pd.DataFrame:
    """
    Computes the Ledoit-Wolf shrinkage covariance matrix of daily returns
    over a trailing window ending on the given date.
    
    Args:
        date: The end date for the trailing window.
        window_days: The number of trading days to include in the window.
        
    Returns:
        A 5x5 pandas DataFrame representing the covariance matrix.
        
    Raises:
        ValueError: If there is not enough data before the given date.
    """
    date = pd.to_datetime(date)
    
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    daily_file = os.path.join(root_dir, "data", "processed", "daily_returns.csv")
    
    df = pd.read_csv(daily_file, index_col="date", parse_dates=["date"])
    
    # Filter rows up to the given date
    df_up_to_date = df.loc[:date]
    
    if len(df_up_to_date) < window_days:
        raise ValueError(f"Not enough data to compute sigma for {date}. "
                         f"Require {window_days} days, got {len(df_up_to_date)}.")
        
    # Take trailing window
    window_df = df_up_to_date.iloc[-window_days:]
    
    # Fit Ledoit-Wolf
    lw = LedoitWolf()
    cov_matrix = lw.fit(window_df).covariance_
    
    return pd.DataFrame(cov_matrix, index=window_df.columns, columns=window_df.columns)

import numpy as np

def caps_for_date(date: str | pd.Timestamp, window_days: int = 252, multiplier: float = 5.0, hard_ceiling: float = 0.40) -> dict[str, float]:
    """
    Derived from the same trailing-window Sigma used for sigma_for_date — no second data
    source. Lower-volatility assets get a larger natural cap share (inverse-volatility
    weighting), scaled by `multiplier`, clipped at `hard_ceiling`.
    """
    sigma = sigma_for_date(date, window_days)
    vol = np.sqrt(np.diag(sigma))
    inv_vol_weights = (1 / vol) / (1 / vol).sum()   # sums to 1
    caps = np.clip(inv_vol_weights * multiplier, a_min=None, a_max=hard_ceiling)
    return dict(zip(sigma.columns, caps))

