import pandas as pd
from data_loader.lookup import sigma_for_date, caps_for_date
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "qaoa-service"))
from fastapi.testclient import TestClient
from app.main import app
from app.solver import brute_force_solver
import time

def run_demo():
    df = pd.read_csv('data/processed/daily_returns.csv')
    latest_date = df['date'].max()
    sigma_df = sigma_for_date(latest_date)
    
    tickers = list(sigma_df.columns)
    caps = caps_for_date(latest_date)
    # The dummy expected return for now
    mu_hat = [0.0] * len(tickers)
    
    req = {
        "tickers": tickers,
        "mu_hat": mu_hat,
        "sigma": sigma_df.values.tolist(),
        "risk_aversion": 1.0,
        "caps": caps,
        "long_only": True,
        "request_id": "demo-run-qaoa"
    }
    
    B = 3
    
    print(f"Running Exact Brute Force Solver for B={B}...")
    t0 = time.perf_counter()
    w_exact, obj_exact = brute_force_solver(tickers, mu_hat, sigma_df.values.tolist(), 1.0, caps, B)
    t1 = time.perf_counter()
    print(f"Exact Solve Time: {(t1 - t0)*1000:.2f} ms")
    print(f"Exact Objective: {obj_exact:.6f}")
    print(f"Exact Weights: {w_exact}")
    print("-" * 40)
    
    client = TestClient(app)
    resp = client.post("/optimize", json=req)
    
    if resp.status_code == 200:
        data = resp.json()
        print("QAOA Optimization successful!")
        print(f"QAOA Solve time: {data['solve_time_ms']:.2f} ms")
        print(f"QAOA Objective: {data['objective_value']:.6f}")
        print(f"QAOA Status: {data['solver_status']}")
        print("QAOA Weights:")
        for t, w in data['weights'].items():
            print(f"  {t}: {w:.4f}")
    else:
        print("Error:")
        print(resp.text)

if __name__ == "__main__":
    run_demo()
