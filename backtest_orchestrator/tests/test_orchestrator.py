import pytest
import pandas as pd
import httpx
import respx
from unittest.mock import patch

from backtest_orchestrator.orchestrator import compute_realized_return, send_optimization_request, run_backtest
from shared_contracts.contracts import OptimizationRequest

def test_turnover_and_rebalance_day_exclusion():
    # Setup dummy returns
    dates = pd.date_range("2024-01-05", "2024-01-12", freq="D") # 01-05 is Friday, 01-12 is Friday
    # returns: 1% daily
    df = pd.DataFrame({"A": [0.01]*len(dates)}, index=dates)
    
    # Rebalance on 01-05. Window for returns is 01-06 to 01-12 (7 days total)
    w = {"A": 1.0}
    
    ret = compute_realized_return(df, pd.to_datetime("2024-01-05"), pd.to_datetime("2024-01-12"), w)
    
    # 7 days of 1% returns compounded = 1.01^7 - 1 = 0.072135
    assert round(ret, 6) == round(1.01**7 - 1, 6)

@respx.mock
def test_byte_identical_request_and_error_handling():
    req = OptimizationRequest(
        tickers=["A"],
        mu_hat=[0.1],
        sigma=[[0.1]],
        risk_aversion=1.0,
        caps={"A": 1.0},
        long_only=True,
        request_id="test"
    )
    
    # Mock Markowitz returns optimal
    markowitz_route = respx.post("http://localhost:8000/optimize").mock(
        return_value=httpx.Response(200, json={
            "request_id": "test",
            "weights": {"A": 1.0},
            "objective_value": 0.1,
            "solve_time_ms": 1.0,
            "solver_status": "optimal",
            "solver_name": "test_m"
        })
    )
    
    # Mock QAOA returns optimal_inaccurate
    qaoa_route = respx.post("http://localhost:8001/optimize").mock(
        return_value=httpx.Response(200, json={
            "request_id": "test",
            "weights": {"A": 1.0},
            "objective_value": 0.09,
            "solve_time_ms": 5.0,
            "solver_status": "optimal_inaccurate",
            "solver_name": "test_q"
        })
    )
    
    with httpx.Client() as client:
        m_res = send_optimization_request(client, "http://localhost:8000/optimize", req)
        q_res = send_optimization_request(client, "http://localhost:8001/optimize", req)
        
    assert m_res.solver_status == "optimal"
    assert q_res.solver_status == "optimal_inaccurate"
    
    # Verify the byte-identical JSON payloads
    m_body = markowitz_route.calls[0].request.content
    q_body = qaoa_route.calls[0].request.content
    assert m_body == q_body
