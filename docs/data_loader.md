# Data Loader

The `data_loader` is a purely functional module responsible for cleaning raw CSV data and computing inputs for the solvers. **No solver service is allowed to import or depend on `data_loader`.**

## Responsibilities

1. **Ingestion & Tidy**: 
   - `build_tidy_returns.py`: A one-shot script that parses the multi-table raw CSV (e.g., Fama-French Industry Portfolios) and converts the daily return section into a standard, decimal-based `daily_returns.csv` indexed by date.
   - Operated via `docker compose run --rm data-loader`.

2. **Lookups (On-Demand)**:
   - `lookup.py`: Exposes pure functions used exclusively by the `backtest_orchestrator`.
   - `sigma_for_date(date, window_days)`: Calculates the empirical covariance matrix $\Sigma$ over a trailing window ending on `date`, utilizing `sklearn.covariance.LedoitWolf` shrinkage to guarantee Positive Semi-Definiteness (PSD) even when $N \approx T$.
   - `caps_for_date(date, window_days)`: Calculates asset upper-bound weights (caps) based on inverse volatility over the trailing window. High volatility assets receive strict allocation caps.

## Design Constraints
The `data_loader` never executes optimizations, holds no state, and makes no network requests. It is simply a data preparation step to guarantee solver independence.
