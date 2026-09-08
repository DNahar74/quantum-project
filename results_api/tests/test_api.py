import pytest
import sqlite3
import os
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient

# Mock DB for testing
TEST_DB = "test_results.db"

# Setup DB path for the app
os.environ["DB_PATH"] = TEST_DB

from app.main import app
from results_store.db import init_db, insert_result, compute_hash

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    
    yield
    
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_hash_sensitivity():
    # "sigma_hash/caps_hash actually differ when the underlying array differs by even one value"
    sigma1 = [[0.01, 0.02], [0.02, 0.03]]
    sigma2 = [[0.01, 0.02], [0.02, 0.0300001]] # Tiny difference
    
    hash1 = compute_hash(sigma1)
    hash2 = compute_hash(sigma2)
    
    assert hash1 != hash2
    
    # "and match when it's identical"
    sigma1_copy = [[0.01, 0.02], [0.02, 0.03]]
    assert hash1 == compute_hash(sigma1_copy)

def test_sharpe_and_drawdown_calculation():
    # Insert hand-computed series
    # Let's say weekly returns: 0.01, -0.01, 0.02
    returns = [0.01, -0.01, 0.02]
    
    for i, r in enumerate(returns):
        insert_result(TEST_DB, {
            "request_id": f"req-{i}",
            "rebalance_date": f"2024-01-0{i+1}",
            "arm_name": "test_arm",
            "weights": {"A": 1.0},
            "turnover": 0.1,
            "realized_return": r,
            "transaction_cost": 0.001,
            "solver_status": "optimal",
            "solve_time_ms": 1.0,
            "sigma_hash": "hash",
            "caps_hash": "hash",
            "risk_aversion": 1.0
        })
        
    res = client.get("/comparison")
    assert res.status_code == 200
    comp = res.json()
    
    assert "test_arm" in comp
    metrics = comp["test_arm"]
    
    # Hand compute metrics
    mean_ret = np.mean(returns)
    std_ret = np.std(returns, ddof=1)
    expected_sharpe = (mean_ret * 52) / (std_ret * np.sqrt(52))
    
    assert np.isclose(metrics["annualized_sharpe"], expected_sharpe)
    
    # Hand compute drawdown
    # cum ret:
    # t0: 1.01 (max 1.01) -> dd = 0
    # t1: 1.01 * 0.99 = 0.9999 (max 1.01) -> dd = (1.01 - 0.9999) / 1.01 = 0.01000099
    # t2: 0.9999 * 1.02 = 1.019898 (max 1.019898) -> dd = 0
    # max dd is approx 0.01
    cum_ret = np.cumprod(1 + np.array(returns))
    running_max = np.maximum.accumulate(cum_ret)
    dd = (running_max - cum_ret) / running_max
    expected_dd = np.max(dd)
    
    assert np.isclose(metrics["max_drawdown"], expected_dd)
    
    assert np.isclose(metrics["avg_turnover"], 0.1)

def test_missing_data_returns_empty():
    # Clear DB
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    init_db(TEST_DB)
    
    # Query an empty DB
    res = client.get("/results")
    assert res.status_code == 200
    assert res.json() == []
    
    res = client.get("/runs")
    assert res.status_code == 200
    assert res.json()["total_requests"] == 0
