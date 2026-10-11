# Quantum vs Classical Portfolio Backtest: Stage 1 Pipeline

## Purpose
The project tests whether the **choice of optimizer** (Markowitz vs QAOA) changes portfolio performance, separately from the return forecast. To make that a fair test, every optimizer gets byte-identical inputs (μ̂, Σ, caps, risk aversion q) on every rebalance date.

Stage 1 uses Fama-French industry portfolio returns and a neural-network forecaster trained offline. Stage 2 will swap in Yahoo Finance data at the data-loader step only.

## Pipeline at a glance

```
12_Industry_Portfolios_Daily.csv   (raw Fama-French file, in repo)
          │
          ▼
[1] data-loader (one-off job)          ──► data/processed/daily_returns.csv
          │                                        │
          ▼                                        ▼
[2] forecaster (one-off job, PyTorch)  ──► data/processed/mu_hat.csv
          │                                        │
          ▼                                        ▼
[3] backtest-orchestrator (one-off job)
      per Friday: Σ, caps (lookup.py) + μ̂ (mu_hat.csv) → one OptimizationRequest
          │                         │
          ▼                         ▼
[4a] markowitz-service       [4b] qaoa-service        (stateless HTTP solvers)
          │                         │
          └──────────┬──────────────┘
                     ▼
[5] results_store (SQLite: results.db)
                     ▼
[6] results-api (read-only HTTP) ──► [7] frontend (React dashboard)

[8] prometheus scrapes /metrics on the services ──► grafana
```

Run order:

```bash
docker compose up -d --build
docker compose run --rm data-loader
docker compose run --rm forecaster
docker compose run --rm backtest-orchestrator
```

---

## [1] Data loader: `data_loader/`

**In:**
- `12_Industry_Portfolios_Daily.csv`, the Ken French multi-table CSV with values in percent. Set `RAW_RETURNS_CSV` to use the 5-industry file instead.

**Transformations** (`build_tidy_returns.py`):
1. Parse only the *Average Value Weighted Returns -- Daily* table (`parse_multitable_csv.py`).
2. Drop days with any missing value.
3. Divide by 100 to turn percent into decimal returns.

**Out:**
- `data/processed/daily_returns.csv`: indexed by `date`, one column per industry (NoDur, Durbl, Manuf, Enrgy, Chems, BusEq, Telcm, Utils, Shops, Hlth, Money, Other). Each value is that day's simple return. It covers 1926-07-01 to 2026-07-31 (26,296 days).

**Also provides** `lookup.py`, which the orchestrator calls on demand:
- `sigma_for_date(date, window=252)`: a Ledoit-Wolf shrinkage covariance of the trailing 252 daily returns up to and including `date`. It is a **daily** covariance, n×n, and raises an error if there are fewer than 252 days of history.
- `caps_for_date(date, window)`: a maximum weight per asset, equal to its inverse-volatility share × 5, clipped at 0.40.

**Never:** downloads anything. It only rereads the raw file.

---

## [2] Forecaster: `forecaster/`

**In:**
- `data/processed/daily_returns.csv` (set with `RETURNS_FILE`).

**Transformations** (`build_mu_hat.py`, the walk-forward run):
1. **Price index:** `prices = (1 + returns).cumprod()`, because the feature code works on prices.
2. **Features** (`features.py`), built separately for each asset from past data only:
   - 10 lagged daily returns
   - rolling mean and rolling volatility over 5, 10 and 20 days
   - 20-day momentum
   - a 20-day z-score of the latest return
3. **Target:** the forward 5-trading-day return, `P[t+5]/P[t] − 1` (`horizon = 5`).
4. **Retrain schedule:** on the first Friday of each year, once 5 years of history exist (96 retrains, 1931 to 2026):
   - The training set is every (date, asset) row whose target was fully realised by that Friday. Nothing after the Friday is used.
   - Split it by date: the first 85% is the train set, the last 15% is the early-stopping set, with a 25-day gap between them (`dataset.py`).
   - Fit a StandardScaler on the train set only.
   - Train one shared MLP for all assets (`model.py`): the features plus a 4-dimensional learned embedding per asset, two hidden layers of 64 and 32 units, MSE loss, Adam, early stopping (`train.py`).
5. **Prediction:** for every Friday until the next retrain, build each asset's feature row from prices up to that Friday only, and predict its 5-day return.

**Out:**
- `data/processed/mu_hat.csv`: indexed by `date` (each rebalance Friday from mid-1931 onward), one column per asset. Each value is the forecast **weekly** return.

**Guarantees:** the tests (`tests/test_forecaster.py`) check two things.
- Changing the returns after date t never changes μ̂ for t.
- Each model only ever sees prices up to its own retrain date.

**Separately:** `python -m forecaster.main` does one train/validation/test run for evaluating the model. It writes metrics, a plot and a checkpoint (weights, asset map, feature names and the fitted scaler) to `forecaster/outputs/`. The backtest doesn't use it.

**Limit:** the model learns one embedding per asset, so a new asset list (5 industries, or Yahoo stocks) means rebuilding `mu_hat.csv`, not reusing a trained model.

---

## [3] Backtest orchestrator: `backtest_orchestrator/`

**In:**
- `daily_returns.csv`
- `mu_hat.csv` (set with `MU_HAT_FILE`)
- the lookup functions from step 1
- settings from environment variables: date range, window (252), risk aversion q (1.0), transaction cost (10 bps)

**For each trading Friday in the date range:**
1. Get the daily Σ and the caps from `lookup.py`. If there's less than 252 days of history, skip the week.
2. Get μ̂ with `get_mu_hat(date, tickers)`. If the date has no row, skip the week (μ̂ is never filled with zeros). If an asset is missing or a value is NaN, stop the run.
3. **Match units:** compute `Σ_weekly = 5 × Σ_daily`, once, so that μ̂ and Σ describe the same period.
4. Hash Σ_weekly, μ̂ and the caps with SHA-256.
5. Build **one** `OptimizationRequest` (tickers, mu_hat, sigma, risk_aversion, caps, long_only, request_id) and POST that same object to both solvers.
6. Score each arm's weights:
   - **Realised return:** each asset's daily returns are compounded from the day after the rebalance through the next Friday, then weighted.
   - **Turnover:** `Σ|w_new − w_prev|`; the first rebalance counts as 1.0.
   - **Net return:** the realised return minus turnover × tcost_bps / 10,000.

**Out:**
- One row per (date, arm) written to results_store.

---

## [4] Solver services: `markowitz-service/`, `qaoa-service/`

**In:**
- an `OptimizationRequest`. The solvers never touch the data files.

**Problem:** maximise `μ̂ᵀw − q·wᵀΣw`, with weights summing to 1, each weight at or below its cap, and long-only.

**Transformations:**
- **Markowitz:** projects Σ to be positive semi-definite, then solves a cvxpy problem with OSQP. The problem is compiled once and reused across dates (warm start). Tiny negative weights are clipped and the weights renormalised.
- **QAOA:** builds a QUBO from exactly `μ̂/B` and `−q·Σ/B²`, with no other rescaling, and runs a simulated QAOA (COBYLA) to choose which assets to hold. Each chosen asset gets an equal weight.

**Out:**
- an `OptimizationResult`: request_id, weights, objective value, solver status (`optimal`, `optimal_inaccurate` or `infeasible`), solver name and `solve_time_ms`.

---

## [5] Results store: `results_store/db.py`

**In:**
- the scored rows from the orchestrator.

**Stores:** a SQLite table `backtest_results` with these columns: request_id, rebalance_date, arm_name, weights (JSON), turnover, realized_return, transaction_cost, solver_status, solve_time_ms, sigma_hash, mu_hat_hash, caps_hash and risk_aversion. Each (date, arm) pair is unique.

**Audit:** both arms should have the same three hashes for a given date, which shows they got identical inputs.

---

## [6] Results API → [7] Frontend
- **results-api:** read-only. `/results` returns the rows, `/comparison` returns per-arm metrics (Sharpe, drawdown, turnover), and there is a summary endpoint.
- **frontend:** a React and Recharts dashboard comparing the arms. It talks only to results-api.

## [8] Monitoring
- Each service exposes `/metrics`: solve latency, solver status counts and request/error rates. Prometheus scrapes them and Grafana shows them.

---

## Configuration
| Variable | Used by | Default |
|---|---|---|
| `RAW_RETURNS_CSV` | data-loader input | `12_Industry_Portfolios_Daily.csv` |
| `RETURNS_CSV` | data-loader output; forecaster and orchestrator input | `daily_returns.csv` |
| `MU_HAT_CSV` | forecaster output; orchestrator input | `mu_hat.csv` |
| `RESULTS_DB` | orchestrator output; results-api input | `results.db` |
| `BACKTEST_START_DATE` / `BACKTEST_END_DATE` | orchestrator | full history |
| `BACKTEST_WINDOW_DAYS`, `BACKTEST_RISK_AVERSION`, `BACKTEST_TCOST_BPS` | orchestrator | 252, 1.0, 10.0 |

## Known Stage 1 caveats (what to tune next)
- **No forecast for the first 5 years:** the backtest effectively starts in mid-1931.
- **Weak forecasts:** on recent data μ̂ correlates only weakly with the realised 5-day returns (−0.11 to 0.24). Features, horizon and model size are the obvious things to tune.
- **Slow build:** the expanding training window takes about 3 hours. A trailing window (for example 20 years) would cut that to about 1 hour, at some cost to how much history the model learns from.
- **Unused recent data:** the last ~30 days before each retrain aren't used (the early-stopping slice is trimmed).
- **Data universe:** the constitution names the 5-industry universe, but the default is 12 industries.
- **Fresh database:** use a new `RESULTS_DB` for this run so leftover zero-μ̂ rows from 1927–1931 don't mix in.

## Stage 2: Yahoo Finance
Only step 1 changes: `data_loader/yahoo_data.py` will download adjusted prices and write the **same** `daily_returns.csv` format. Everything after that stays the same, but `mu_hat.csv` must be rebuilt because the asset list changes. The forecaster and backtest never download anything.
