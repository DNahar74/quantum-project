# Architecture Overview

This project is a modular, microservices-based backtesting pipeline comparing classical Markowitz Mean-Variance optimization with Quantum Approximate Optimization Algorithm (QAOA) based cardinality-constrained portfolio selection.

For the end-to-end data flow (inputs, outputs and transformations of every module), see **[Pipeline](pipeline.md)**.

## Core Modules

1. **[Data Loader](data_loader.md)**: Ingests raw Fama-French industry portfolios, builds tidy trailing window returns, and provides pure functions for covariance ($\Sigma$) and asset caps lookups.
2. **[Backtest Orchestrator](backtest_orchestrator.md)**: The strict control layer ensuring both solver arms receive cryptographically identical optimization requests across every historical rebalance date.
3. **[Solver Services](solvers.md)**: 
   - `markowitz-service`: Continuous long-only QP solver (CVXPY / OSQP).
   - `qaoa-service`: QUBO combinatorial subset solver (Qiskit QAOA & Exact Brute Force).
4. **[Results Backend](results_backend.md)**: Immutable SQLite store populated by the orchestrator, served via a read-only FastAPI layer (`results-api`).
5. **[Frontend Dashboard](frontend.md)**: A dumb, view-only React/Recharts UI that plots the performance metrics (Turnover, Drawdown, Sharpe, Allocation) of both arms.

## System Flow

1. Raw CSV data $\rightarrow$ `data_loader` $\rightarrow$ `daily_returns.csv`.
2. `backtest_orchestrator` steps through dates $\rightarrow$ calls `data_loader.lookup` $\rightarrow$ builds `OptimizationRequest`.
3. `OptimizationRequest` $\rightarrow$ POST to `markowitz-service` and POST to `qaoa-service`.
4. Solvers compute weights $\rightarrow$ Return `OptimizationResult`.
5. Orchestrator calculates realized returns and turnover $\rightarrow$ writes to `results_store` (SQLite).
6. User visits `frontend` $\rightarrow$ UI fetches JSON from `results-api` $\rightarrow$ UI renders charts.
