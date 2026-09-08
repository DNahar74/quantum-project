import pandas as pd
import numpy as np
import httpx
import logging
from typing import Dict, Any, List
import uuid
import sys
import os
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Setup path so we can import data_loader
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_loader.lookup import sigma_for_date, caps_for_date
from backtest_orchestrator.config import settings
from backtest_orchestrator.forecaster import get_mu_hat
from shared_contracts.contracts import OptimizationRequest, OptimizationResult
from results_store.db import init_db, insert_result, compute_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backtest")

@retry(wait=wait_exponential(multiplier=1, min=1, max=10),
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type(httpx.RequestError))
def send_optimization_request(client: httpx.Client, url: str, req: OptimizationRequest) -> OptimizationResult:
    resp = client.post(url, json=req.model_dump())
    resp.raise_for_status()
    return OptimizationResult.model_validate(resp.json())

def compute_realized_return(
    returns_df: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    weights: Dict[str, float]
) -> float:
    """
    Computes portfolio return from day after start_date up to and including end_date.
    """
    # Exclude start_date (the rebalance day itself)
    mask = (returns_df.index > start_date) & (returns_df.index <= end_date)
    period_returns = returns_df.loc[mask]
    
    if period_returns.empty:
        return 0.0
        
    # Compound returns for each asset
    # (1 + r1) * (1 + r2) ... - 1
    asset_compounded = (1.0 + period_returns).prod() - 1.0
    
    port_return = 0.0
    for t, w in weights.items():
        if t in asset_compounded:
            port_return += w * asset_compounded[t]
            
    return port_return

def run_backtest():
    db_path = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "results.db"))
    init_db(db_path)
    
    daily_file = os.environ.get("RETURNS_FILE", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "processed", "daily_returns.csv"))
    returns_df = pd.read_csv(daily_file, index_col="date", parse_dates=["date"])
    
    start_date = pd.to_datetime(settings.start_date)
    end_date = pd.to_datetime(settings.end_date)
    
    mask = (returns_df.index >= start_date) & (returns_df.index <= end_date)
    backtest_period = returns_df.loc[mask]
    
    # Identify Friday rebalance dates
    # dayofweek == 4 is Friday
    fridays = backtest_period[backtest_period.index.dayofweek == 4].index.tolist()
    
    if not fridays:
        logger.warning("No Fridays found in backtest period.")
        return pd.DataFrame()
        
    # We need pairs of rebalance dates to compute realized returns
    # Add a final dummy date (end_date) if it's past the last Friday to capture the last partial week,
    # or just only evaluate up to the last Friday. We'll evaluate up to the last Friday.
    
    results = []
    
    # State tracking
    prev_weights = {"markowitz": {}, "qaoa": {}}
    
    with httpx.Client(timeout=30.0) as client:
        for i in range(len(fridays)):
            reb_date = fridays[i]
            
            try:
                sigma_df = sigma_for_date(reb_date, settings.window_days)
                caps = caps_for_date(reb_date, settings.window_days)
            except ValueError as e:
                logger.warning(f"Skipping {reb_date} due to missing data: {e}")
                continue
                
            tickers = list(sigma_df.columns)
            mu_hat = get_mu_hat(reb_date, tickers)
            
            req_id = f"reb-{reb_date.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
            
            # Formulate the single request
            req = OptimizationRequest(
                tickers=tickers,
                mu_hat=mu_hat,
                sigma=sigma_df.values.tolist(),
                risk_aversion=settings.risk_aversion,
                caps=caps,
                long_only=True,
                request_id=req_id
            )
            
            arm_responses = {}
            for arm, url in [("markowitz", settings.markowitz_url), ("qaoa", settings.qaoa_url)]:
                try:
                    res = send_optimization_request(client, url, req)
                    arm_responses[arm] = res
                    if res.solver_status != "optimal":
                        logger.warning(f"Arm {arm} returned status {res.solver_status} for date {reb_date}")
                except Exception as e:
                    logger.error(f"Arm {arm} failed completely on {reb_date}: {e}")
                    arm_responses[arm] = None
                    
            # Compute next rebalance date to define the return window
            next_date = fridays[i+1] if i + 1 < len(fridays) else end_date
            
            for arm in ["markowitz", "qaoa"]:
                res = arm_responses.get(arm)
                if not res:
                    continue
                    
                w = res.weights
                
                # Turnover
                turnover = 0.0
                if prev_weights[arm]:
                    for t in tickers:
                        turnover += abs(w.get(t, 0.0) - prev_weights[arm].get(t, 0.0))
                else:
                    turnover = 1.0 # Initial allocation is 100% turnover
                    
                prev_weights[arm] = w
                
                # Realized return
                gross_ret = compute_realized_return(returns_df, reb_date, next_date, w)
                
                # Transaction cost
                tcost = (settings.tcost_bps / 10000.0) * turnover
                net_ret = gross_ret - tcost
                
                
                sigma_hash = compute_hash(sigma_df.values.tolist())
                caps_hash = compute_hash(caps)
                
                res_dict = {
                    "request_id": res.request_id,
                    "rebalance_date": reb_date.strftime('%Y-%m-%d'),
                    "arm_name": arm,
                    "weights": w,
                    "turnover": turnover,
                    "realized_return": net_ret,
                    "transaction_cost": tcost,
                    "solver_status": res.solver_status,
                    "solve_time_ms": res.solve_time_ms,
                    "sigma_hash": sigma_hash,
                    "caps_hash": caps_hash,
                    "risk_aversion": settings.risk_aversion
                }
                results.append(res_dict)
                insert_result(db_path, res_dict)
                
    results_df = pd.DataFrame(results)
    return results_df

if __name__ == "__main__":
    df = run_backtest()
    if not df.empty:
        print("Backtest complete. Saved to SQLite database.")
        print(df.head(10))
    else:
        print("Backtest yielded no results.")
