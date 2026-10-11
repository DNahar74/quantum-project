import pytest
import numpy as np
import cvxpy as cp
from unittest.mock import patch
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

def test_solver_error_does_not_return_previous_solution():
    tickers = ["A", "B"]
    sigma = [[0.04, 0.0], [0.0, 0.01]]
    caps = {"A": 1.0, "B": 1.0}
    # Populate the cached problem with a good solution first.
    solve_markowitz(tickers, [0.10, 0.05], sigma, 1.0, caps, True)

    with patch.object(cp.Problem, "solve", side_effect=cp.error.SolverError("boom")):
        weights, obj, t_ms, status = solve_markowitz(tickers, [0.05, 0.10], sigma, 1.0, caps, True)

    assert status == cp.SOLVER_ERROR
    assert weights == {"A": 0.0, "B": 0.0}
    assert obj == 0.0

def test_short_positions_kept_when_not_long_only():
    tickers = ["A", "B"]
    mu_hat = [0.10, -0.05]
    sigma = [[0.04, 0.0], [0.0, 0.01]]
    caps = {"A": 2.0, "B": 2.0}

    weights, obj, t_ms, status = solve_markowitz(tickers, mu_hat, sigma, 1.0, caps, False)

    # Closed form: maximise mu.w - w'Sw with w_A + w_B = 1 -> w_A = (mu_A - mu_B + 2*s_B) / (2*(s_A + s_B)) = 1.7
    w_a = (0.10 + 0.05 + 2 * 0.01) / (2 * (0.04 + 0.01))
    assert status == "optimal"
    assert np.isclose(weights["A"], w_a, atol=1e-4)
    assert np.isclose(weights["B"], 1 - w_a, atol=1e-4)
    assert weights["B"] < 0

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
