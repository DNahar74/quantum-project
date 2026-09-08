import sys
import os
import sqlite3
import pandas as pd
import numpy as np
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Results API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "results.db"))

def get_db_connection():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=503, detail="Database not found. Run orchestrator first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/runs")
def get_runs():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT MIN(rebalance_date) as start_date, 
               MAX(rebalance_date) as end_date,
               COUNT(DISTINCT request_id) as total_requests
        FROM backtest_results
    """)
    row = c.fetchone()
    conn.close()
    if row and row['total_requests'] > 0:
        return dict(row)
    return {"start_date": None, "end_date": None, "total_requests": 0}

@app.get("/results")
def get_results(arm: str = None, from_date: str = None, to_date: str = None):
    conn = get_db_connection()
    
    query = "SELECT * FROM backtest_results WHERE 1=1"
    params = []
    
    if arm:
        query += " AND arm_name = ?"
        params.append(arm)
    if from_date:
        query += " AND rebalance_date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND rebalance_date <= ?"
        params.append(to_date)
        
    query += " ORDER BY rebalance_date ASC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # "results-api never returns a 200 with partial/stale data silently — a missing date range in results-store should be visible in the response (empty list, not a fabricated gap-fill)"
    # We return the empty list if no data, which is fine.
    
    # Parse json weights
    if not df.empty:
        df["weights"] = df["weights"].apply(json.loads)
        
    return df.to_dict(orient="records")

@app.get("/comparison")
def get_comparison(from_date: str = None, to_date: str = None):
    conn = get_db_connection()
    
    query = "SELECT rebalance_date, arm_name, realized_return, turnover FROM backtest_results WHERE 1=1"
    params = []
    
    if from_date:
        query += " AND rebalance_date >= ?"
        params.append(from_date)
    if to_date:
        query += " AND rebalance_date <= ?"
        params.append(to_date)
        
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if df.empty:
        return {}
        
    comparison = {}
    
    for arm, group in df.groupby("arm_name"):
        group = group.sort_values("rebalance_date")
        returns = group["realized_return"].values
        turnovers = group["turnover"].values
        
        # Annualized Sharpe: mean * 52 / (std * sqrt(52)) since weekly
        # Handle zero std
        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1) if len(returns) > 1 else 0.0
        
        if std_ret > 0:
            sharpe = (mean_ret * 52) / (std_ret * np.sqrt(52))
        else:
            sharpe = 0.0
            
        # Max drawdown
        # Compute cumulative product of (1 + returns)
        cum_ret = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_ret)
        drawdown = (running_max - cum_ret) / running_max
        max_dd = np.max(drawdown) if len(drawdown) > 0 else 0.0
        
        avg_turnover = np.mean(turnovers)
        
        comparison[arm] = {
            "annualized_sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
            "avg_turnover": float(avg_turnover)
        }
        
    return comparison
