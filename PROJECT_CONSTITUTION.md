# Project constitution — quantum-enhanced portfolio optimization benchmark

This document governs every module built for this project: data-loader, markowitz-service,
qaoa-service (and any later optimizer arm), results-store, results-api, frontend, and monitoring.
Read this in full before writing any code. When a specific build prompt conflicts with this
document, this document wins unless the prompt explicitly says it's amending the constitution.

## 1. The research question this project must not compromise

We are isolating whether *optimizer choice* (Markowitz vs QAOA vs future arms) drives portfolio
performance differences, independent of the return forecast. This only holds if every optimizer
arm receives **byte-identical** `mu_hat`, `sigma`, and `risk_aversion` for a given rebalance date.

**Non-negotiable**: no solver-specific code path may transform, rescale, re-derive, or
"improve" its copy of these inputs. If an optimizer needs a different internal representation
(e.g. QAOA needs a QUBO matrix), that transformation must be a pure, documented function of the
shared inputs — never a separate estimation.

## 2. Data sources — real, fixed, no substitutions

Two files, both Fama-French 5 Industry Portfolios (Cnsmr, Manuf, HiTec, Hlth, Other):

- `5_Industry_Portfolios_Daily.csv` — daily value-weighted returns. Used for: Sigma estimation,
  and as the base series resampled to weekly for rebalance-date realized returns.
- `5_Industry_Portfolios.csv` — monthly file. Used ONLY for its `Average Firm Size` and
  `Number of Firms in Portfolios` tables (→ market equity per industry → caps). Its returns
  tables are not used elsewhere in this project — the daily file is the return source of truth.

Both are multi-table CSVs (several labeled sections separated by blank lines in one file).
The data-loader must parse by locating each section header, never by fixed line-number offsets,
since a re-downloaded file may shift line counts slightly.

**No synthetic data. No other tickers. No silently substituting a different public dataset**
if one of these proves inconvenient — flag the inconvenience instead of routing around it.

## 3. Rebalancing and estimation frequency

- **Rebalance cadence: weekly** (resampled Friday-to-Friday from the daily file).
- **Estimation window: trailing daily returns**, not weekly-resampled returns — more data points
  produce a more stable Sigma, even though rebalancing itself happens weekly. Default window:
  252 trading days, configurable.
- **Caps**: derived once (or refreshed on a monthly cadence matching the source file), not
  recomputed per rebalance — market equity shares don't need weekly refresh at this data grain.
- The realized-return calculation for any rebalance period must exclude the rebalance day itself
  from the "held at new weights" window (no double-counting the trade day).

## 4. The shared contract — defined once, imported everywhere

```python
class OptimizationRequest(BaseModel):
    tickers: list[str]            # ["Cnsmr","Manuf","HiTec","Hlth","Other"]
    mu_hat: list[float]
    sigma: list[list[float]]
    risk_aversion: float          # q — identical across every optimizer arm for a given run
    caps: dict[str, float]        # per-asset max weight, from market-equity share
    long_only: bool = True
    request_id: str               # ties back to the exact mu_hat/sigma/q version used

class OptimizationResult(BaseModel):
    request_id: str
    weights: dict[str, float]
    objective_value: float
    solve_time_ms: float
    solver_status: str
    solver_name: str
```

This lives in one `shared-contracts` package. **No service defines its own version of these
models.** If a field needs to change, it changes here first, and every consumer updates together.

## 5. Module boundaries

- **data-loader**: offline script, not a running service. Reads the two raw CSVs and writes two
  clean, tidy, date-indexed artifacts to `data/processed/`: `daily_returns.csv` (from the daily
  file's value-weighted returns table) and `market_equity_monthly.csv` (from the monthly file's
  firm-size × firm-count tables). It also provides a shared `lookup.py` module with two pure
  functions — `sigma_for_date(date, window_days)` and `caps_for_date(date)` — that compute Sigma
  from a trailing window and caps from the nearest prior month, on demand. **These functions are
  imported only by the backtest harness (or any other orchestrator that assembles requests) —
  never by markowitz-service, qaoa-service, or any future solver service.** Solver services must
  have zero dependency on data_loader; they only ever see a fully-assembled `OptimizationRequest`
  with sigma/caps already filled in. This is what makes "identical inputs across arms" a
  structural guarantee (one Python object sent to both services) rather than a convention two
  services are separately trusted to honor. Re-run the parsing step manually when source files
  update. Never fetches data over the network at request time.
- **markowitz-service / qaoa-service / [future arms]**: stateless FastAPI services. Pure function
  of `OptimizationRequest → OptimizationResult`. No global state, no reading files mid-request
  beyond what's passed in. Each is independently deployable and independently testable.
- **mu_hat is out of scope for every module above** until explicitly wired in. Until then, a
  documented placeholder (e.g. zero vector) is used and labeled as such in `_meta` — never
  silently treated as a real forecast in any report or dashboard.
- **results-store**: the only place `OptimizationResult` rows persist. Solvers write here;
  nothing else writes here.
- **results-api**: thin read-only layer over results-store, for the frontend. Never proxies to
  the solver services directly.
- **frontend**: reads only from results-api. Never calls markowitz-service/qaoa-service directly,
  never embeds solver logic.

## 6. Code quality bar (applies to every service)

- Full type hints, docstrings on every public function.
- Input validation at the API boundary (reject malformed Sigma — non-symmetric, wrong shape,
  NaNs — with a clear 4xx, not a downstream solver crash).
- `ruff` + `black` + `mypy` clean in CI before merge.
- No `print()` for anything meant to be observed later — structured logging only.
- No hardcoded paths, secrets, or hostnames — `pydantic-settings` reads from environment.

## 7. Numerical correctness requirements

- Sigma must be PSD-safe before any solver consumes it (shrink or PSD-project if needed).
- Every result's `solver_status` must be checked by the caller; `optimal_inaccurate` is logged
  as a warning and surfaced in the frontend, never silently treated as `optimal`.
- Test suite must include: a closed-form 2-asset QP sanity check, a KKT-residual check on solved
  output, property-based tests (weights sum to ~1, all ≥ 0 under long-only, objective ≥ equal-weight
  baseline), and cross-solver agreement (OSQP vs ECOS/Clarabel) within tolerance.

## 8. Performance requirements

- Warm-start solves across consecutive rebalance dates where the solver backend supports it.
- Use `cp.Parameter` for mu_hat/Sigma in cvxpy-based solvers so problem structure compiles once.
- `solve_time_ms` is a required field on every result — this is a research metric
  (computational cost comparison), not just an ops nicety, so it must never be dropped or optional.

## 9. Docker requirements

- One Dockerfile per service, multi-stage (builder + slim runtime).
- Non-root user in every container.
- `.dockerignore` excludes `__pycache__`, `.git`, notebooks, local venvs.
- Every service exposes `/health`, wired into compose `healthcheck:`.
- Single `docker-compose.yml` at repo root. No Kubernetes, no unnecessary orchestration
  complexity for a project this size — resist the urge to over-engineer here.
- Dependencies pinned exactly (lockfile), per service.

## 10. Monitoring

- Every service exposes `/metrics` (Prometheus format) via middleware — solve latency (p50/p95),
  solver status counts, request/error rate.
- Prometheus scrapes both solver services every 15s.
- Grafana reads from Prometheus. This dashboard answers "is the system healthy right now" —
  it is an ops view, not a research-results view, and must not be conflated with the frontend.

## 11. Frontend

- Stack: React + Recharts, talking only to results-api.
- Required pages: comparison overview (Sharpe/drawdown/turnover, grouped bar, all arms),
  cumulative returns (multi-line), allocation over time (stacked area, per arm), drawdown
  (shaded area), run history (table with run parameters and links into results).
- Never renders solver internals (QUBO matrices, cvxpy objects) — only the shared
  `OptimizationResult` shape and derived time series.

## 12. Versioning and audit trail

Every `OptimizationResult` must be traceable to the exact `sigma`/`caps` artifact version and
`risk_aversion` used to produce it. This is what lets a later report claim "arms received
identical inputs" as a verified fact rather than an assumption.

## 13. Build sequence — do not skip ahead

1. data-loader (parses both CSVs → tidy `daily_returns.csv` + `market_equity_monthly.csv`,
   plus shared `sigma_for_date` / `caps_for_date` lookup functions)
2. markowitz-service (+ Prometheus middleware)
3. qaoa-service
4. results-store / results-api
5. frontend
6. docker-compose tying all of the above together
7. Grafana dashboard provisioning

Each step should be buildable and testable in isolation before the next begins. A later prompt
for step N may assume steps 1..N-1 already exist and satisfy this constitution — it should not
need to re-specify contract shape, docker conventions, or code-quality bar already defined here.

## 14. What the agent must never do

- Invent or substitute a different dataset because the specified one is inconvenient to parse.
- Add binary/cardinality variables to the Markowitz QP — it is a continuous, long-only,
  convex mean-variance problem, full stop, unless this constitution is explicitly amended.
- Fetch data over the network at request time in any service.
- Let a solver-specific transformation silently change mu_hat, Sigma, or risk_aversion for
  that arm relative to what every other arm received.
- Treat a placeholder mu_hat as if it were a real forecast in any output, log, or dashboard.