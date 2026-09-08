import time
import numpy as np
import cvxpy as cp
from typing import Tuple, Dict

# Global cache for problems to support warm starts and compiled parameterization
_problem_cache = {}

def project_psd(sigma: np.ndarray, tolerance: float = 1e-8) -> np.ndarray:
    """Ensure the matrix is exactly symmetric and positive semi-definite."""
    sigma = (sigma + sigma.T) / 2.0
    eigvals, eigvecs = np.linalg.eigh(sigma)
    if np.any(eigvals < -tolerance):
        eigvals = np.maximum(eigvals, 0.0)
        sigma = eigvecs @ np.diag(eigvals) @ eigvecs.T
        sigma = (sigma + sigma.T) / 2.0
    return sigma

def get_or_create_problem(n: int, long_only: bool) -> Tuple[cp.Problem, Dict[str, cp.Parameter], cp.Variable]:
    cache_key = (n, long_only)
    if cache_key in _problem_cache:
        return _problem_cache[cache_key]
        
    w = cp.Variable(n)
    
    mu_hat_param = cp.Parameter(n)
    sigma_param = cp.Parameter((n, n), PSD=True)
    q_param = cp.Parameter(nonneg=True)
    caps_param = cp.Parameter(n, nonneg=True)
    
    objective = cp.Maximize(mu_hat_param.T @ w - q_param * cp.quad_form(w, sigma_param))
    
    constraints = [
        cp.sum(w) == 1.0,
        w <= caps_param
    ]
    if long_only:
        constraints.append(w >= 0)
        
    problem = cp.Problem(objective, constraints)
    
    params = {
        "mu_hat": mu_hat_param,
        "sigma": sigma_param,
        "q": q_param,
        "caps": caps_param
    }
    
    _problem_cache[cache_key] = (problem, params, w)
    return problem, params, w

def solve_markowitz(
    tickers: list[str],
    mu_hat: list[float],
    sigma: list[list[float]],
    risk_aversion: float,
    caps: dict[str, float],
    long_only: bool,
    solver: str = cp.OSQP
) -> Tuple[dict[str, float], float, float, str]:
    """
    Core pure function to solve the Markowitz problem.
    Returns: weights_dict, objective_value, solve_time_ms, solver_status
    """
    n = len(tickers)
    
    # Convert inputs to numpy arrays
    mu_hat_arr = np.array(mu_hat, dtype=float)
    sigma_arr = np.array(sigma, dtype=float)
    
    # Project to PSD to ensure cvxpy accepts it
    sigma_arr = project_psd(sigma_arr)
    
    caps_arr = np.array([caps[t] for t in tickers], dtype=float)
    
    problem, params, w = get_or_create_problem(n, long_only)
    
    # Assign values
    params["mu_hat"].value = mu_hat_arr
    params["sigma"].value = sigma_arr
    params["q"].value = risk_aversion
    params["caps"].value = caps_arr
    
    start_time = time.perf_counter()
    
    # Suppress output, use OSQP or Clarabel/ECOS
    try:
        problem.solve(solver=solver, warm_start=True)
    except Exception as e:
        # e.g., solver failure
        pass
        
    solve_time_ms = (time.perf_counter() - start_time) * 1000.0
    
    status = problem.status if problem.status is not None else "failed"
    
    w_val = w.value
    if w_val is None:
        # If solver completely failed to find anything, fallback to zeros
        w_val = np.zeros(n)
        obj_val = 0.0
    else:
        # Clip numerical noise to 0 and renormalize
        w_val = np.maximum(w_val, 0.0)
        sum_w = np.sum(w_val)
        if sum_w > 0:
            w_val = w_val / sum_w
            
        # Re-evaluate objective with cleaned weights
        obj_val = (mu_hat_arr.T @ w_val - risk_aversion * (w_val.T @ sigma_arr @ w_val)).item()
        
    weights_dict = {t: float(w_val[i]) for i, t in enumerate(tickers)}
    return weights_dict, obj_val, solve_time_ms, status
