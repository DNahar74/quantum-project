import pandas as pd
from data_loader.lookup import sigma_for_date, caps_for_date
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "markowitz-service"))
from fastapi.testclient import TestClient
from app.main import app

def run_demo():
    # Setup data
    df = pd.read_csv('data/processed/daily_returns.csv')
    latest_date = df['date'].max()
    sigma_df = sigma_for_date(latest_date)
    
    tickers = list(sigma_df.columns)
    caps = caps_for_date(latest_date)
    print("Derived Inverse-Volatility Caps:")
    for t, c in caps.items():
        print(f"  {t}: {c:.4f}")
    mu_hat = [0.0] * len(tickers)
    
    req = {
        "tickers": tickers,
        "mu_hat": mu_hat,
        "sigma": sigma_df.values.tolist(),
        "risk_aversion": 1.0,
        "caps": caps,
        "long_only": True,
        "request_id": "demo-run-1"
    }
    
    client = TestClient(app)
    resp = client.post("/optimize", json=req)
    
    if resp.status_code == 200:
        data = resp.json()
        print("Optimization successful!")
        print(f"Solve time: {data['solve_time_ms']:.2f} ms")
        print(f"Status: {data['solver_status']}")
        print("Weights:")
        for t, w in data['weights'].items():
            print(f"  {t}: {w:.4f}")
    else:
        print("Error:")
        print(resp.text)

if __name__ == "__main__":
    run_demo()
