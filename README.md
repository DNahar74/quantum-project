# Quantum Portfolio Optimization Pipeline

This project simulates a weekly portfolio backtest comparing classical Markowitz Mean-Variance Optimization against a Quantum Approximate Optimization Algorithm (QAOA) subset selector, using historical Fama-French industry returns.

For how the pipeline and both optimizers work, see [ARCHITECTURE.md](ARCHITECTURE.md). For known issues and open design questions, see [REVIEW.md](REVIEW.md).

## Prerequisites

1. **Docker Desktop** installed and running.
2. Ensure you have allocated at least 4GB of RAM and sufficient disk space to your Docker VM.

## Quickstart

Follow these exact steps to spin up the services and run the backtest locally:

### 1. Start the Core Services
Start the frontend, APIs, and optimization solvers in the background. Note that `qaoa-service` compiles Qiskit primitives on startup and may take 30-60 seconds to become healthy.

```bash
docker compose up -d --build
```

You can check the health of the services using `docker compose ps`. Wait until both `markowitz-service` and `qaoa-service` report as `(healthy)`.

### 2. Prepare the Dataset
The raw Fama-French CSV needs to be cleaned and formatted into a structured daily returns CSV. We run this one-off task using the `data-loader` profile:

```bash
docker compose run --rm data-loader
```
*(This will output: `Successfully built tidy returns at /app/data/processed/daily_returns.csv`)*

### 2b. Build the Return Forecasts
The neural-network forecaster trains walk-forward on the processed returns (one retrain per year) and writes one week-ahead expected-return vector per rebalance Friday to `data/processed/mu_hat.csv`. Rerun it whenever the returns file changes:

```bash
docker compose run --rm forecaster
```
*(Fridays in the first five years of data have no forecast and are skipped by the backtest.)*

### 3. Run the Backtest Orchestrator
The orchestrator drives the backtest. It loops through the historical Fridays, calculates trailing 252-day covariance matrices, and hits both optimization solvers concurrently. The results are stored in a persistent SQLite database volume.

```bash
docker compose run --rm backtest-orchestrator
```
*(Depending on the dataset size and QAOA reps, this may take a couple of minutes. It will print "Backtest complete. Saved to SQLite database." when finished.)*

### 4. View the Dashboard
Once the backtest is complete, open your browser to view the interactive results:

**http://localhost:8080**

### Running another dataset
Steps 2–4 use the 12-industry file by default. To run the 5-industry file without overwriting those results, give it its own processed file and results database. Put these in a `.env` file next to `docker-compose.yml`, or pass them with `docker compose --env-file <file>`:

```bash
RAW_RETURNS_CSV=5_Industry_Portfolios_Daily.csv
RETURNS_CSV=daily_returns_5_industry.csv
RESULTS_DB=results_5_industry.db
```

Then repeat steps 2 and 3, and run `docker compose up -d results-api` so the dashboard reads the new database. Remove the variables and run `docker compose up -d results-api` again to switch back. See [ARCHITECTURE.md](ARCHITECTURE.md#configuration-and-datasets) for details.

## Troubleshooting

- **Container is unhealthy**: If `qaoa-service` fails to start, ensure Docker has enough memory. Qiskit can be memory intensive during the QAOA compilation.
- **Docker Read-Only File System**: If you see `input/output error` or `read-only file system` crashes during build/run, your Docker WSL2 disk image is likely out of space. Run `docker system prune -a --volumes` to clear old cache layers.
- **Empty Dashboard**: If the dashboard is running but empty, ensure Step 3 completed successfully. The `results-api` requires the orchestrator to populate the database volume first.
