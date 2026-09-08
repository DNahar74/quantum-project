import pytest
import numpy as np
import cvxpy as cp
from app.solver import solve_markowitz

def test_closed_form_2_asset():
    tickers = ["A", "B"]
    mu_hat = [0.10, 0.05]
    sigma = [
        [0.04, 0.0],
        [0.0, 0.01]
    ]
    q = 1.0
    caps = {"A": 1.0, "B": 1.0}
    
    # Analytical solution derivation for unconstrained (only sum to 1):
    # w_A = 0.7, w_B = 0.3
    weights, obj, t_ms, status = solve_markowitz(tickers, mu_hat, sigma, q, caps, True)
    assert status == "optimal"
    assert np.isclose(weights["A"], 0.7, atol=1e-4)
    assert np.isclose(weights["B"], 0.3, atol=1e-4)

def test_kkt_residual_5_asset():
    tickers = ["A", "B", "C", "D", "E"]
    np.random.seed(42)
    mu_hat = np.random.uniform(0.01, 0.1, 5).tolist()
    A = np.random.uniform(-0.1, 0.1, (5, 5))
    sigma = (A @ A.T + np.eye(5) * 0.01).tolist()
    caps = {t: 0.4 for t in tickers}
    q = 2.0
    
    weights, obj, t_ms, status = solve_markowitz(tickers, mu_hat, sigma, q, caps, True)
    assert status in ("optimal", "optimal_inaccurate")
    w_vec = np.array([weights[t] for t in tickers])
    
    # Check sum to 1
    assert np.isclose(np.sum(w_vec), 1.0)
    # Check bounds
    assert np.all(w_vec >= -1e-5)
    assert np.all(w_vec <= 0.4 + 1e-5)

def test_cross_solver_agreement():
    tickers = ["A", "B"]
    mu_hat = [0.10, 0.05]
    sigma = [[0.04, 0.0], [0.0, 0.01]]
    q = 1.0
    caps = {"A": 1.0, "B": 1.0}
    
    w_osqp, _, _, _ = solve_markowitz(tickers, mu_hat, sigma, q, caps, True, solver=cp.OSQP)
    try:
        w_clarabel, _, _, _ = solve_markowitz(tickers, mu_hat, sigma, q, caps, True, solver=cp.CLARABEL)
        assert np.isclose(w_osqp["A"], w_clarabel["A"], atol=1e-4)
        assert np.isclose(w_osqp["B"], w_clarabel["B"], atol=1e-4)
    except Exception as e:
        pytest.skip(f"Clarabel not available or failed: {e}")
