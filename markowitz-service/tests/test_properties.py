import numpy as np
from hypothesis import given, settings
from hypothesis.strategies import floats, lists, dictionaries
from app.solver import solve_markowitz
import pytest

# Generate valid problem inputs
def valid_inputs():
    from hypothesis.strategies import tuples
    return tuples(
        lists(floats(min_value=-0.1, max_value=0.1), min_size=3, max_size=3), # mu_hat
        lists(floats(min_value=0.1, max_value=1.0), min_size=3, max_size=3) # caps
    )

@settings(deadline=None, max_examples=50)
@given(valid_inputs())
def test_properties(inputs):
    mu_hat, raw_caps = inputs
    n = len(mu_hat)
    tickers = [f"T{i}" for i in range(n)]
    caps = {t: cap for t, cap in zip(tickers, raw_caps)}
    
    # Generate PSD sigma
    A = np.random.uniform(-0.1, 0.1, (n, n))
    sigma = (A @ A.T + np.eye(n) * 0.01).tolist()
    q = 1.0
    
    weights, obj, t_ms, status = solve_markowitz(tickers, mu_hat, sigma, q, caps, True)
    
    if status in ("optimal", "optimal_inaccurate"):
        w_vec = np.array([weights[t] for t in tickers])
        # Sums to ~1
        assert np.isclose(np.sum(w_vec), 1.0)
        # Bounded between 0 and caps
        for i, t in enumerate(tickers):
            assert w_vec[i] >= -1e-4
            assert w_vec[i] <= caps[t] + 1e-4
            
        # Compare to equal-weight baseline (if equal weight is feasible)
        eq_w = np.ones(n) / n
        if np.all(eq_w <= np.array(raw_caps)):
            eq_obj = (np.array(mu_hat).T @ eq_w - q * (eq_w.T @ np.array(sigma) @ eq_w)).item()
            # The optimized objective should be >= equal weight objective
            assert obj >= eq_obj - 1e-5
