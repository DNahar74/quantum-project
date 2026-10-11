# Architecture

How the backtest pipeline is put together, what each service does, and how the two optimizer arms (Markowitz and QAOA) are implemented. For setup steps see [README.md](README.md); for known issues and open design questions see [REVIEW.md](REVIEW.md). The project rules every module follows are in [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md).

## Contents

- [What the pipeline answers](#what-the-pipeline-answers)
- [System overview](#system-overview)
- [One rebalance, step by step](#one-rebalance-step-by-step)
- [Data loader](#data-loader)
- [Shared contract](#shared-contract)
- [Backtest orchestrator](#backtest-orchestrator)
- [Markowitz service](#markowitz-service)
- [QAOA service](#qaoa-service)
- [Results store and results API](#results-store-and-results-api)
- [Frontend](#frontend)
- [Monitoring](#monitoring)
- [Configuration and datasets](#configuration-and-datasets)
- [Testing](#testing)

## What the pipeline answers

Each week, two portfolio optimizers receive *identical* inputs (expected returns, covariance, risk aversion and per-asset caps) and each picks a portfolio. The pipeline then measures what each portfolio actually earned over the following week, net of transaction costs, across decades of Fama-French industry returns. The intent is to compare optimizers while holding every input fixed.

- **Markowitz:** classical continuous mean-variance optimization. Any weights within the caps.
- **QAOA:** a quantum algorithm (simulated classically) that chooses *which* assets to hold, each at an equal weight.

## System overview

```
                       ┌──────────────────────────────┐
 Fama-French CSV ─────►│ data-loader (one-off job)    │──► processed returns CSV
                       └──────────────────────────────┘          │ (processed_data volume)
                                                                 ├──► forecaster (one-off job) ──► mu_hat CSV
                                                                 ▼                                    │
                       ┌──────────────────────────────┐   sigma, caps, mu_hat per Friday ◄───────────┘
                       │ backtest-orchestrator (job)  │◄── data_loader/lookup.py
                       │  for each trading Friday:    │
                       │   build OptimizationRequest  │── same request ──┬─────────────┐
                       │   score both portfolios      │                  ▼             ▼
                       └──────────────┬───────────────┘        markowitz-service  qaoa-service
                                      │ rows                   (cvxpy / OSQP)     (QAOA, NumPy)
                                      ▼
                              results_store (SQLite, results_data volume)
                                      │
                                      ▼
                              results-api (read-only) ──► frontend (React dashboard)

  prometheus ── scrapes /metrics on markowitz-service, qaoa-service, results-api ──► grafana
```

| Component | Kind | Port (host → container) | Tech |
|---|---|---|---|
| `data-loader` | one-off job (`tools` profile) | none | pandas |
| `forecaster` | one-off job (`tools` profile) | none | PyTorch, scikit-learn, pandas |
| `backtest-orchestrator` | one-off job (`tools` profile) | none | pandas, httpx, tenacity, scikit-learn |
| `markowitz-service` | HTTP service | 8000 → 8000 | FastAPI, cvxpy + OSQP |
| `qaoa-service` | HTTP service | 8001 → 8000 | FastAPI, NumPy, qiskit-algorithms (COBYLA) |
| `results-api` | HTTP service | 8002 → 8000 | FastAPI, pandas, SQLite |
| `frontend` | static site | 8080 → 8080 | React, Recharts, Vite, nginx |
| `prometheus` | monitoring | 9090 → 9090 | Prometheus |
| `grafana` | monitoring | 3001 → 3000 | Grafana |

Every service runs as a non-root user, exposes `/health` (wired into compose health checks) and, for the FastAPI services, `/metrics`.

## One rebalance, step by step

For every trading Friday in the backtest window:

1. **Estimate risk.** `sigma_for_date` fits a Ledoit-Wolf shrinkage covariance on the trailing 252 trading days of daily returns, up to and including that Friday. Weeks without 252 days of history are skipped.
2. **Set caps.** `caps_for_date` gives each asset a maximum weight: its inverse-volatility share × 5, clipped at 0.40.
3. **Expected returns.** `get_mu_hat` reads that Friday's row from `mu_hat.csv`, written offline by `python -m forecaster.build_mu_hat`. Each value forecasts the asset's return over the next 5 trading days. A model is retrained on the first Friday of each year on everything known at that close, and each Friday's forecast uses prices up to that Friday only. Fridays with no row (the first five years) are skipped, never filled with zeros.
4. **Match units.** μ̂ is a weekly return and sigma a daily covariance, so the orchestrator multiplies sigma by 5 once, before the request is built. Both arms see the same weekly sigma, and `sigma_hash` is taken on it.
5. **Ask both optimizers.** One `OptimizationRequest` object is sent to Markowitz, then to QAOA. Identical inputs are guaranteed by construction, not by convention.
6. **Score each portfolio.**
   - *Realized return:* the portfolio is held from the day after the rebalance through the next rebalance Friday, with each asset's daily returns compounded.
   - *Turnover:* `Σ|w_new − w_prev|`; the first rebalance counts as 1.0.
   - *Cost:* turnover × `tcost_bps` / 10,000, subtracted from the return.
6. **Store a row per arm** with the weights, return, turnover, cost, solver status, solve time, SHA-256 hashes of sigma and caps, and risk aversion.

## Data loader

[`data_loader/`](data_loader/) turns the raw Fama-French file into the clean daily returns everything else uses, and provides the per-date lookups.

- **[parse_multitable_csv.py](data_loader/parse_multitable_csv.py):** Fama-French files hold several tables in one CSV. The parser finds a section by its header text, never by line number, reads it until the next blank line, converts −99.99 / −999 to missing, and parses `YYYYMMDD` or `YYYYMM` dates.
- **[build_tidy_returns.py](data_loader/build_tidy_returns.py):** reads the *Average Value Weighted Returns -- Daily* section of any industry file (5, 12 or more industries, kept in file order). It drops incomplete days, converts percent to decimals, and writes the processed CSV. `RAW_RETURNS_FILE` and `RETURNS_FILE` choose the input and output.
- **[lookup.py](data_loader/lookup.py):** `sigma_for_date` and `caps_for_date` read the processed file named by `RETURNS_FILE`, the same file the orchestrator uses for realized returns. The parsed file is cached in memory and re-read only when it changes on disk.

Solver services never import the data loader. They only see a fully assembled request.

## Shared contract

[`shared_contracts/contracts.py`](shared_contracts/contracts.py) defines the two messages every arm speaks:

```python
class OptimizationRequest(BaseModel):
    tickers: List[str]
    mu_hat: List[float]
    sigma: List[List[float]]
    risk_aversion: float          # q, identical across arms
    caps: Dict[str, float]        # per-asset max weight
    long_only: bool = True
    request_id: str

class OptimizationResult(BaseModel):
    request_id: str
    weights: Dict[str, float]
    objective_value: float
    solve_time_ms: float          # a research metric, never optional
    solver_status: str            # "optimal", "optimal_inaccurate", "infeasible", "solver_error"
    solver_name: str              # "cvxpy_osqp" or "qiskit_qaoa"
```

Both services validate requests at the boundary before solving. Malformed input gets a 422: mismatched lengths, a non-square or asymmetric sigma (tolerance 1e-5), NaN or infinite values, or a missing cap.

Every arm optimizes the same mean-variance objective:

$$\max_w \; \hat\mu^\top w - q\, w^\top \Sigma w \quad \text{s.t.}\quad \textstyle\sum_i w_i = 1,\; w_i \le \text{cap}_i,\; w_i \ge 0$$

The arms differ in which weights they're allowed to choose and how they search.

## Backtest orchestrator

[`backtest_orchestrator/orchestrator.py`](backtest_orchestrator/orchestrator.py) runs as a one-shot job.

- **Window:** `resolve_backtest_bounds` uses `BACKTEST_START_DATE` / `BACKTEST_END_DATE` when set and the full history otherwise, clamped to the data.
- **Rebalance dates:** every trading day that falls on a Friday.
- **Calls:** sequential HTTP requests with `httpx`. A request that fails at the network level is retried up to 3 times with exponential backoff (`tenacity`). The timeout is `BACKTEST_REQUEST_TIMEOUT` (default 300 s).
- **Failures:** if an arm fails completely, that week has no row for that arm, and the next turnover is measured against its last successful weights.
- **Settings** ([config.py](backtest_orchestrator/config.py), prefix `BACKTEST_`): window days (252), transaction cost (10 bps), risk aversion (1.0), solver URLs, timeout.

## Markowitz service

[`markowitz-service/app/solver.py`](markowitz-service/app/solver.py) is the classical arm: a convex quadratic program solved with cvxpy and OSQP.

### Formulation

Exactly the shared objective above, with continuous weights. Long-only adds `w ≥ 0`; the cap and budget constraints always apply.

### Implementation

1. **PSD safety.** `project_psd` symmetrizes sigma and, if any eigenvalue is below −1e-8, clips negative eigenvalues to zero and rebuilds the matrix. This is the constitution's §7 requirement, and it keeps cvxpy's `quad_form` convex.
2. **Compile once, reuse.** `get_or_create_problem(n, long_only)` builds the cvxpy problem with `cp.Parameter`s for `mu_hat`, `sigma` (declared PSD), `q` and `caps`, and caches it per `(n, long_only)`. Later rebalances only assign new parameter values, so cvxpy compiles the problem once and OSQP can warm-start from the previous week's solution.
3. **Solve.** `problem.solve(solver=OSQP, warm_start=True)`. The solver is a parameter, so Clarabel or ECOS can be swapped in; a test checks that OSQP and Clarabel agree.
4. **Failure handling.** If the solve raises, the service returns `solver_error` with zero weights. This matters with a cached problem: cvxpy raises before unpacking, so the previous request's values are still sitting on the problem object. Infeasible problems (caps summing below 1) return cvxpy's `infeasible` status with zero weights.
5. **Clean-up.** For long-only requests, tiny negative values from solver tolerance are clipped to zero and the weights renormalized to sum to 1. The objective is then recomputed from the cleaned weights, so the reported value matches the reported portfolio.

`solver_name` is `cvxpy_osqp`. A typical solve takes a few milliseconds.

### What it tends to choose

With `mu_hat = 0` the problem is constrained minimum variance. It usually holds most of the low-volatility assets in unequal amounts, often with one or two positions at the 0.40 cap.

## QAOA service

[`qaoa-service/app/solver.py`](qaoa-service/app/solver.py) is the quantum arm: QAOA (the Quantum Approximate Optimization Algorithm) choosing which assets to hold. The circuit is simulated exactly on a classical machine.

### Formulation: equal-weight selection with a cardinality sweep

QAOA works on binary variables, so the service restricts the portfolio to **B assets held at weight 1/B each**. With $x_i \in \{0,1\}$ and $w = x / B$, the shared objective becomes

$$f(x) = \frac{1}{B}\hat\mu^\top x - \frac{q}{B^2}\, x^\top \Sigma x \quad \text{s.t.}\quad \textstyle\sum_i x_i = B.$$

- **Caps by eligibility.** An asset can be held at 1/B only if its cap is at least 1/B. Each cardinality's problem includes only the eligible assets, so caps cost no extra qubits.
- **Cardinality sweep.** The service tries every cardinality B the caps allow, solves each, and keeps the B with the best objective. The number of holdings comes from the data. With caps at 0.40 the minimum is 3 assets, since 1/B ≤ 0.40 requires B ≥ 3.
- **Untransformed inputs.** The QUBO coefficients are exactly `mu_hat / B` and `−q·sigma / B²`. A test intercepts the QUBO builder to confirm the shared inputs are never rescaled, as constitution §1 requires.

### From objective to QUBO

`_qubo` turns "maximize f(x) subject to Σx = B" into an unconstrained energy to minimize:

$$E(x) = -f(x) + \lambda\Big(\textstyle\sum_i x_i - B\Big)^2$$

- **Penalty λ.** Defaults to 2 × the objective's span: the most f can vary, the same bound qiskit-optimization uses. Qiskit's own automatic penalty is 1 + span. With daily covariances around 1e-4 that is about 1,000× the objective, and QAOA would only learn "pick B assets", not which ones.
- **Normalization.** The QUBO is divided by its largest coefficient. This positive rescaling doesn't change the minimizer, and it keeps QAOA's angles working on energies of order 1.
- **Same result as Qiskit.** A test checks the energies equal qiskit-optimization's `QuadraticProgramToQubo` up to a positive scale and a constant, including the default penalty.

### The QAOA run

`_qaoa_select` handles one problem of k ≤ `max_qubits` assets:

1. **Energies.** Compute E for all 2^k bitstrings at once with NumPy. Basis state i has qubit j = bit j of i, the ordering Qiskit uses.
2. **Circuit.** `_qaoa_circuit` simulates the QAOA state exactly. It starts in the uniform superposition |+⟩^k. Each of `reps` layers (p, default 1) applies:
   - the cost layer $e^{-i\gamma E}$, a phase per bitstring;
   - the mixer $e^{-i\beta \sum_j X_j}$, which is RX(2β) on every qubit.
3. **Angles.** COBYLA (from qiskit-algorithms, up to 100 evaluations, starting at π/4) adjusts (γ, β) to minimize the expected energy.
4. **Decode.** From the final distribution, keep bitstrings with probability ≥ 1e-6 that satisfy Σx = B, and return the lowest-energy one. This is the same rule as qiskit-optimization's `MinimumEigenOptimizer`. Its probability is reported as `p_solution`.

**Why NumPy instead of Qiskit's simulator.** Because the cost layer is diagonal, the state can be computed directly instead of gate by gate. The mixer applies the same RX to every qubit, so it factors into two small dense matrices, one per half of the qubits. Entry (i, j) of RX(2β) on m qubits is cos(β)^(m−d) · (−i·sin β)^d, where d is the number of bits in which i and j differ. That bit-difference matrix is computed once per run. A test checks the resulting probabilities equal Qiskit's `QAOAAnsatz` simulated on Aer, to within 1e-12, for 1–3 layers. Going through Qiskit itself cost 4–118 ms per circuit evaluation and 23–52 ms per QUBO build. The NumPy version takes about 0.3 ms at 10 qubits, which is what makes large universes practical.

### Any universe size: block search

A simulated register grows as 2^k, so no single QAOA run uses more than `max_qubits` qubits (default 10). When a cardinality has more eligible assets than that, `_block_search` solves it in pieces:

1. **Greedy start.** Add assets one at a time, each with the best marginal gain, until B are held.
2. **Blocks.** Split held assets into chunks and unheld assets into chunks so each held + unheld pair fits in `max_qubits`. For each pair, fix every other asset and re-solve the block with QAOA. Fixed held assets enter the block's linear terms through their covariance with the block. Keep any change that improves the full objective.
3. **Stop.** After a full round in which every pair was tried with no improvement.

Every held/unheld pair shares a block in each round, and each block is solved to its best valid bitstring. So the result is **swap-optimal**: no single swap of a held asset for an unheld one improves it. In tests, and in 60 random benchmark universes of 11–16 assets with deliberately small blocks, it equalled the brute-force optimum every time.

| Assets | Time per request | QAOA runs | Widest register |
|---|---|---|---|
| 5 | ~0.01 s | 2 | 5 qubits |
| 12 | 0.2–0.4 s | ~35 | 10 qubits |
| 30 | ~4 s | ~210 | 10 qubits |
| 49 | ~17 s | ~830 | 10 qubits |

These figures need `scipy==1.15.3`, which is pinned. From 1.16, scipy's COBYLA is pure Python and about 10× slower.

### Status and metadata

- **Status:** `optimal` when every candidate cardinality produced a solution, `optimal_inaccurate` if some QAOA run sampled no valid bitstring, and `infeasible` (zero weights) when the caps allow no cardinality at all.
- **Metadata** (logged by the service, not part of the API response):
  - `B`, `B_candidates`, `objective_by_B`: the chosen cardinality, the ones tried, and each one's objective.
  - `block_search_B`: cardinalities solved in blocks.
  - `max_qubits`, `n_qubits`: the register limit and the widest register actually simulated.
  - `qaoa_runs`, `n_layers`, `optimizer`.
  - `p_solution`: the probability QAOA gave the returned bitstring.
- **Exact baseline.** `brute_force_solver` enumerates every cap-feasible equal-weight subset and is used by tests and `demo_qaoa.py`.

### Reading the results

- **QAOA can't beat Markowitz on the in-sample objective.** Equal-weight portfolios are a subset of the portfolios Markowitz may choose. Out-of-sample differences reflect both the optimizer and the equal-weight restriction.
- **The answer rarely depends on QAOA's angle tuning.** At up to 10 qubits, the decode rule effectively checks every bitstring, so each run returns its problem's best valid answer however well the angles were tuned. `p_solution` shows how much probability QAOA itself put on that answer.

## Results store and results API

- **[results_store/db.py](results_store/db.py):** one SQLite table, `backtest_results`, with a row per (rebalance date, arm). It holds the weights as JSON, turnover, realized return net of cost, transaction cost, solver status, solve time, sigma and caps hashes, and risk aversion. Rows are written with `INSERT OR REPLACE` on `UNIQUE(rebalance_date, arm_name)`. Give each experiment its own database file, as `RESULTS_DB` does below.
- **[results_api/app/main.py](results_api/app/main.py):** a read-only FastAPI layer over that database. It never calls the solvers.

| Endpoint | Returns |
|---|---|
| `GET /runs` | first and last rebalance date and request count |
| `GET /results?arm=&from_date=&to_date=` | the stored rows, weights parsed |
| `GET /comparison?from_date=&to_date=` | per arm: annualized Sharpe (weekly × √52), max drawdown, average turnover |

## Frontend

[`frontend/`](frontend/) is a React + Recharts single-page app served by nginx. It reads only from the results API (`VITE_API_URL`, default `http://localhost:8002`).

| Route | Page |
|---|---|
| `/` | Comparison overview: Sharpe, drawdown and turnover per arm |
| `/cumulative` | Cumulative returns, with markers on weeks a solver wasn't `optimal` |
| `/allocation` | Allocation over time (stacked area, per arm) |
| `/drawdown` | Drawdown chart |
| `/history` | Rebalance history with solver statuses |

## Monitoring

Every FastAPI service exposes Prometheus metrics at `/metrics` via `prometheus-fastapi-instrumentator`: request counts, latency histograms and status codes. Prometheus ([prometheus.yml](prometheus.yml)) scrapes both solver services and the results API on their container port, 8000. Grafana runs alongside but has no provisioned dashboards yet. This is an operations view; research results live in the frontend.

## Configuration and datasets

Compose variables (also listed in [.env.example](.env.example)) choose the dataset without code changes. Defaults reproduce the 12-industry setup.

| Variable | Used by | Default |
|---|---|---|
| `RAW_RETURNS_CSV` | data-loader input | `12_Industry_Portfolios_Daily.csv` |
| `RETURNS_CSV` | data-loader output, forecaster and orchestrator input | `daily_returns.csv` |
| `MU_HAT_CSV` | forecaster output, orchestrator input | `mu_hat.csv` |
| `RESULTS_DB` | orchestrator output, results-api input | `results.db` |
| `BACKTEST_START_DATE`, `BACKTEST_END_DATE` | orchestrator | full history |
| `BACKTEST_RISK_AVERSION`, `BACKTEST_TCOST_BPS`, `BACKTEST_WINDOW_DAYS` | orchestrator | 1.0, 10.0, 252 |

To run the 5-industry dataset side by side with the default:

```bash
export RAW_RETURNS_CSV=5_Industry_Portfolios_Daily.csv
export RETURNS_CSV=daily_returns_5_industry.csv
export MU_HAT_CSV=mu_hat_5_industry.csv
export RESULTS_DB=results_5_industry.db
docker compose run --rm data-loader
docker compose run --rm forecaster
docker compose run --rm backtest-orchestrator
docker compose up -d results-api     # dashboard now shows the 5-industry run
```

Unset the four variables and run `docker compose up -d results-api` again to switch the dashboard back.

## Testing

| Suite | Covers | Run from |
|---|---|---|
| `markowitz-service/tests` | closed-form 2-asset solution, constraint checks, OSQP vs Clarabel agreement, property tests (hypothesis), solver-error handling, short positions, API validation | `markowitz-service/` |
| `qaoa-service/tests` | equality with Qiskit/Aer and qiskit-optimization, brute-force agreement up to 17 assets, block search, universes of 3–49 assets, caps, determinism, untransformed inputs, API | `qaoa-service/` |
| `results_api/tests` | endpoints, hash sensitivity | repo root |
| `backtest_orchestrator/tests` | rebalance-day exclusion, turnover, backtest bounds, retries | repo root |
| `tests/` | multi-table parsing, processed returns, sigma and caps, building any industry file | repo root |
