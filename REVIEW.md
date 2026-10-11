# Project Review

A full pass over every module in this repository: what each part does, what's broken, what's risky, and what needs a decision before the backtest results can support the research question in [PROJECT_CONSTITUTION.md](PROJECT_CONSTITUTION.md).

- **Reviewed:** commit `5e8f473` on `qaoa-dev`, plus the fixes listed under [Fixed in this change](#fixed-in-this-change)
- **Date:** 2026-10-08
- **Not verified:** anything that needs Docker. The review environment couldn't reach Docker, so tests ran in a Python 3.12 env with each service's pinned dependencies.

## Contents

- [How the pieces fit](#how-the-pieces-fit)
- [Test status](#test-status)
- [Fixed in this change](#fixed-in-this-change)
- [Open: needs a decision](#open-needs-a-decision)
- [Open: correctness and metrics](#open-correctness-and-metrics)
- [Open: operations](#open-operations)
- [Open: docs and housekeeping](#open-docs-and-housekeeping)
- [QAOA service notes](#qaoa-service-notes)
- [Suggested next steps](#suggested-next-steps)

## How the pieces fit

```
12_Industry_Portfolios_Daily.csv
  └─ data_loader/build_tidy_returns.py ──► data/processed/daily_returns.csv
                                              │
backtest_orchestrator (every trading Friday)  │
  ├─ data_loader/lookup.py: sigma_for_date, caps_for_date ◄─┘
  ├─ forecaster.get_mu_hat: zero vector (placeholder)
  ├─ one OptimizationRequest ──► markowitz-service  (cvxpy / OSQP)
  │                          └─► qaoa-service       (equal-weight QAOA)
  └─ realized return, turnover, cost ──► results_store (SQLite)
                                              │
results_api (/runs, /results, /comparison) ◄──┘ ──► frontend (React + Recharts)
prometheus ──► scrapes /metrics on the services ──► grafana
```

Both solver arms receive the same request object, so "identical inputs across arms" is guaranteed by construction.

## Test status

All suites pass after this change: 57 tests.

| Suite | Tests | Run from |
|---|---|---|
| `markowitz-service/tests` | 11 | `markowitz-service/` |
| `qaoa-service/tests` | 35 (about 45 s; includes a 49-asset run) | `qaoa-service/` |
| `results_api/tests` | 3 | repo root only (imports `results_store`) |
| `backtest_orchestrator/tests` | 3 | repo root |
| `tests/` (data loader) | 5 | repo root |

```bash
(cd markowitz-service && python -m pytest tests)
(cd qaoa-service && python -m pytest tests)
python -m pytest results_api/tests backtest_orchestrator/tests tests
```

## Fixed in this change

| # | Problem | Fix |
|---|---|---|
| 1 | **The frontend couldn't be built from a clean clone.** The root `.gitignore` entry `lib/` (from a Python template) also matched `frontend/src/lib/`, so the API client, types, hooks and theme files were never committed. | Scoped the entries to `/lib/` and `/lib64/`. **The files still need committing:** `git add frontend/src/lib`. |
| 2 | **QAOA metrics were never collected.** [prometheus.yml](prometheus.yml) scraped `qaoa-service:8001`, but the container listens on 8000; 8001 is only the host port. [.env.example](.env.example) had the same wrong port in `BACKTEST_QAOA_URL`. | Both now use port 8000. |
| 3 | **Markowitz could return the previous week's portfolio.** The solver swallowed exceptions from `problem.solve`. cvxpy raises before unpacking a failed solve, so `problem.status` and `w.value` on the cached problem still held the previous request's solution, which was returned as this week's. | A failed solve now returns status `solver_error` and zero weights. Covered by a new test. |
| 4 | **Markowitz forced long-only.** Negative weights were clipped to zero even when `long_only=False`. | Clipping and renormalising now happen only for long-only requests. Covered by a closed-form test with a short position. |
| — | **Orchestrator test never ran.** `test_resolve_backtest_bounds_uses_full_historical_window` used `np` without importing numpy. That hid a wrong expectation: it wanted the start moved to early 2021, which matches no lookback rule. | Added the import. The test now checks the documented behaviour (full history by default, early weeks skipped by the loop) and that explicit bounds are clamped to the data. |
| — | **Data loader tests were stale.** They still expected the 5-industry columns and a 5×5 sigma. | Updated to the 12 industries `build_tidy_returns` writes. |

## Open: needs a decision

These decide whether the results can answer the research question. They're design choices, not bugs.

1. **The comparison measures the problem setup, not the optimizer.** The constitution (§1) says the project isolates the effect of *optimizer choice*. But the QAOA arm can only hold equal weights (1/B each), which is a subset of what Markowitz may choose, so Markowitz always scores at least as well in-sample. On 2024-03-29:

   | Arm | Holdings | Objective |
   |---|---|---|
   | Markowitz | 8 assets, unequal weights | −3.66e-5 |
   | QAOA | 3 assets at 1/3 each | −3.99e-5 |

   Any out-of-sample difference mixes the optimizer with the constraint. Options: give Markowitz the same equal-weight cardinality constraint, add a classical exact or heuristic arm on the QAOA formulation, or restate the research question.
2. **Both arms are pure minimum variance.** `mu_hat` is the zero placeholder ([forecaster.py](backtest_orchestrator/forecaster.py)), so `risk_aversion` has no effect on either arm. The constitution (§5) also requires the placeholder to be labelled in outputs. Nothing in the results store or frontend records it.
3. **Caps don't come from market equity.** The contract comment and constitution say caps come from market-equity shares. [lookup.py](data_loader/lookup.py) uses inverse volatility × 5, capped at 0.40. [build_tidy_market_equity.py](data_loader/build_tidy_market_equity.py) reads `5_Industry_Portfolios.csv`, which isn't in the repo, using 5-industry columns.
4. **The default dataset differs from the constitution.** The constitution specifies the Fama-French 5-industry data and forbids substituting a dataset. The pipeline defaults to 12 industries. It can now run either file side by side (see [ARCHITECTURE.md](ARCHITECTURE.md#configuration-and-datasets)), but the default and the constitution should agree.

## Open: correctness and metrics

5. **Containers can't write to fresh volumes (confirmed).** The data loader and orchestrator run as a non-root user, but their mount points (`/app/data/processed`, `/app/results_store_data`) don't exist in the images, so Docker creates new volumes owned by root with mode 755. Running the data-loader image against a brand-new volume fails with `PermissionError: ... /app/data/processed/daily_returns.csv`. Existing setups work only if the volume directories were opened up (the current ones are mode 777). Fix: `mkdir -p` those directories in the data-loader, orchestrator and results-api Dockerfiles before the `chown`, so new volumes inherit the user's ownership.
6. **The two arms can be scored over different weeks.** If one solver call fails, that week is simply missing for that arm. `/comparison` then computes Sharpe and drawdown over different date sets, and the frontend's cumulative-return chart treats the gap as a 0% week.
7. **Max drawdown misses a loss in the first week.** In [results_api/app/main.py](results_api/app/main.py) the running maximum starts at the first cumulative value instead of 1.0. The frontend's drawdown chart gets this right.
8. **Turnover ignores drift.** It compares this week's target weights with last week's target weights, not with the weights after a week of price moves.
9. **Holiday Fridays become two-week holds.** Rebalances run only on Fridays that are trading days. In the full history, 196 weeks have no Friday trading day, so the previous portfolio is held for two weeks.

## Open: operations

10. **The default backtest takes far longer than the README says.** The default range is now the full 1926–2026 history: 5,027 Friday rebalances. The sigma and caps lookups alone take about 0.23 s per rebalance, because `daily_returns.csv` is re-read twice each time. The README still says "a couple of minutes" and calls the solver requests concurrent; they're sequential.
11. **Re-runs overwrite earlier runs.** [results_store/db.py](results_store/db.py) uses `UNIQUE(rebalance_date, arm_name)` with `INSERT OR REPLACE` and has no run ID. A run with different parameters replaces the previous one, and the Run History page can't show separate runs (constitution §11).
12. **The Markowitz problem cache is shared module state.** In [markowitz-service/app/solver.py](markowitz-service/app/solver.py), FastAPI runs sync endpoints in a thread pool, so two concurrent requests with the same number of assets would overwrite each other's parameters. The orchestrator is sequential today, so this hasn't triggered. The constitution also forbids global state in solver services.
13. **Smaller items:**
    - Grafana has no provisioned dashboards (constitution build step 7).
    - Prometheus scrapes every 10 s; the constitution says 15 s.
    - The results API allows any CORS origin with credentials.
    - `results-api` waits for both solvers to be healthy, though it never calls them.
    - `frontend/tsconfig.json` sets `noImplicitAny: false`, weakening type checks.

## Open: docs and housekeeping

- [docs/solvers.md](docs/solvers.md) still describes a fixed cardinality B, a "most probable bitstring" decode and circuit simulation on qiskit-aer. [ARCHITECTURE.md](ARCHITECTURE.md) describes both solvers as they are now; update or remove `docs/solvers.md`.
- [data_loader/requirements.txt](data_loader/requirements.txt) is missing scikit-learn, which `lookup.py` imports.
- `.env.example` still defaults to the 2024-Q1 window, while `docker-compose.yml` now defaults to the full history.
- Commit `5e8f473` is titled "integer granularity formulation", but it contains the block-search solver that replaced that formulation.

## QAOA service notes

What [qaoa-service/app/solver.py](qaoa-service/app/solver.py) does now:

- **Formulation.** One qubit per asset, equal weights 1/B. For each cardinality B the caps allow (assets with cap < 1/B are left out), QAOA picks exactly B assets. The B with the best Markowitz objective wins, so the number of holdings comes from the data instead of a hardcoded 3.
- **Any universe size.** No QAOA run simulates more than `max_qubits` (default 10) qubits. A cardinality with more eligible assets is solved in blocks: start from a greedy pick, re-solve blocks of held plus unheld assets with QAOA while the rest stay fixed, and repeat until a full round finds nothing better. The result is guaranteed swap-optimal: no single swap of a held asset for an unheld one improves it.

  | Assets | Time per request |
  |---|---|
  | 12 (real data) | 0.2–0.4 s |
  | 30 | about 4 s |
  | 49 | about 17 s |

  Up to 17 assets, and in every forced block-search test, results equal brute force.
- **Simulation.** The QUBO and the QAOA circuit are built and simulated in NumPy. Tests check both against Qiskit's `QuadraticProgramToQubo` and its `QAOAAnsatz` simulated on Aer, matching to within 1e-12. Running Qiskit itself in the loop cost 4–118 ms per circuit evaluation and 23–52 ms per QUBO build, too slow for hundreds of block solves.
- **scipy is pinned to 1.15.3.** From 1.16, scipy's COBYLA is pure Python and about 10× slower: 30 assets took 39 s instead of 3.7 s.
- **Caveat for the write-up.** Each QAOA run returns the best valid bitstring the circuit gives non-negligible probability (probability ≥ 1e-6, the same rule as qiskit's `MinimumEigenOptimizer`). At 10 qubits that is effectively every bitstring, so the answer rarely depends on how well QAOA tuned its angles. `metadata["p_solution"]` records the probability QAOA put on the returned bitstring (typically 0.1–0.6%).

## Suggested next steps

1. Commit `frontend/src/lib/` together with the fixes above.
2. Decide items 1–4. They determine what the backtest results can claim.
3. Fix items 6, 10 and 11 before trusting any full-history run.
4. Fix item 5 so a fresh checkout works in Docker, then update `docs/solvers.md`.
