"""
main.py
=======
Single-split run of the NN Return Forecaster on the data loader's returns,
for evaluating the model (the backtest's mu_hat comes from build_mu_hat.py):

    daily_returns.csv -> price index -> features -> chronological split
    -> train NN -> evaluate on held-out test set -> latest mu_hat -> export

Run from the repo root with:
    python -m forecaster.main

Everything is driven by config.py; RETURNS_FILE overrides the input file.
"""

from __future__ import annotations
import os
import json

from forecaster.config import PATHS, DATA, MODEL
from forecaster.build_mu_hat import DEFAULT_RETURNS_FILE, load_price_index
from forecaster.features import build_feature_panel, build_latest_feature_row
from forecaster.dataset import chronological_split
from forecaster.train import train_forecaster
from forecaster.evaluate import evaluate_test_set
from forecaster.forecast import get_mu_hat, export_mu_hat, save_forecaster


def main():
    os.makedirs(PATHS.output_dir, exist_ok=True)
    print("Working directory:", os.getcwd())
    print("Output directory:", os.path.abspath(PATHS.output_dir))

    print("=" * 70)
    print("STEP 1/6 — Loading the data loader's daily returns as a price index")
    print("=" * 70)

    returns_file = os.environ.get("RETURNS_FILE", DEFAULT_RETURNS_FILE)
    prices = load_price_index(returns_file)

    print(f"Prices shape: {prices.shape}  (dates x assets)")

    print("\n" + "=" * 70)
    print("STEP 2/6 — Building leakage-safe feature panel")
    print("=" * 70)
    panel = build_feature_panel(prices)
    print(f"Panel shape: {panel.shape}  (rows = date x asset pairs)")

    print("\n" + "=" * 70)
    print("STEP 3/6 — Chronological train/val/test split")
    print("=" * 70)
    bundle = chronological_split(panel)
    print(f"Train: {len(bundle.train):5d} rows | "
          f"Val: {len(bundle.val):5d} rows | "
          f"Test: {len(bundle.test):5d} rows")

    print("\n" + "=" * 70)
    print("STEP 4/6 — Training the NN forecaster")
    print("=" * 70)
    model, history = train_forecaster(bundle)
    save_forecaster(model, bundle, PATHS.model_path, MODEL)
    print(f"Saved trained model -> {PATHS.model_path}")

    print("\n" + "=" * 70)
    print("STEP 5/6 — Evaluating on held-out TEST set")
    print("=" * 70)
    metrics = evaluate_test_set(model, bundle, PATHS.metrics_json, PATHS.eval_plot)
    print(json.dumps(metrics, indent=2))
    print(f"Saved actual-vs-predicted plot -> {PATHS.eval_plot}")
    print(f"Saved metrics -> {PATHS.metrics_json}")

    print("\n" + "=" * 70)
    print("STEP 6/6 — Producing mu_hat (the optimizer-facing output)")
    print("=" * 70)
    latest_rows = build_latest_feature_row(prices, DATA)
    mu_hat = get_mu_hat(model, latest_rows, bundle)
    export_mu_hat(mu_hat, PATHS.mu_hat_csv, PATHS.mu_hat_json)

    print("mu_hat (predicted next-period return per asset):")
    print(mu_hat.to_string())
    print(f"\nSaved mu_hat -> {PATHS.mu_hat_csv}")
    print(f"Saved mu_hat -> {PATHS.mu_hat_json}")

    print("\nDone. mu_hat is now ready to be consumed unchanged by the")
    print("Markowitz and QAOA optimizer modules (see forecast.load_mu_hat).")


if __name__ == "__main__":
    main()
