# Results Store and API

## Results Store
A persistent SQLite database (`results.db`) mapped via a Docker volume.

- **Schema**: Stores `request_id`, `rebalance_date`, `arm_name`, `weights` (JSON), `turnover`, `realized_return`, `transaction_cost`, `solver_status`, `solve_time_ms`, `sigma_hash`, `mu_hat_hash`, `caps_hash`, and `risk_aversion`.
- **Integrity**: The `sigma_hash`, `mu_hat_hash` and `caps_hash` fields act as a cryptographic audit trail proving both arms received identical inputs for any given `request_id`.
- **Write Access**: ONLY the `backtest_orchestrator` has write access to the store. 

## Results API
A thin, stateless, read-only FastAPI service that interfaces between the SQLite DB and the Frontend Dashboard.

- Exposes endpoints like `/api/v1/results/runs` and `/api/v1/results/comparison`.
- Formats and aggregates the SQLite rows into time-series JSON payloads optimized for Recharts (e.g. pivoting rows so that multiple arms appear as keys in a single date object).
- Does not contain any business logic, calculations, or execution paths.
