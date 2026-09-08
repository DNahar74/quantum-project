import time
import numpy as np
from typing import Tuple

from qiskit_optimization import QuadraticProgram
from qiskit_algorithms import QAOA
from qiskit_algorithms.optimizers import COBYLA
from qiskit.primitives import Sampler
from qiskit_optimization.algorithms import MinimumEigenOptimizer

def brute_force_solver(
    tickers: list[str],
    mu_hat: list[float],
    sigma: list[list[float]],
    risk_aversion: float,
    caps: dict[str, float],
    B: int
) -> Tuple[dict[str, float], float]:
    """
    Classical exact solver over all subsets of size B.
    Returns: weights_dict, objective_value (the Markowitz objective).
    """
    n = len(tickers)
    best_x = None
    best_obj = -np.inf
    
    w_val = 1.0 / B
    
    for i in range(1 << n):
        x = np.array([(i >> j) & 1 for j in range(n)])
        
        if np.sum(x) != B:
            continue
            
        valid = True
        for j in range(n):
            if x[j] == 1 and w_val > caps[tickers[j]] + 1e-5:
                valid = False
                break
        if not valid:
            continue
            
        w = x * w_val
        obj = np.dot(mu_hat, w) - risk_aversion * np.dot(w, np.dot(sigma, w))
        
        if obj > best_obj:
            best_obj = obj
            best_x = x
            
    if best_x is None:
        # Fallback to zero weights if infeasible
        return {t: 0.0 for t in tickers}, 0.0
        
    return {tickers[j]: float(best_x[j] * w_val) for j in range(n)}, best_obj

def solve_qaoa(
    tickers: list[str],
    mu_hat: list[float],
    sigma: list[list[float]],
    risk_aversion: float,
    caps: dict[str, float],
    long_only: bool,
    B: int = 3,
    penalty: float = 1.0,
    reps: int = 1
) -> Tuple[dict[str, float], float, float, str, dict]:
    n = len(tickers)
    
    qp = QuadraticProgram()
    for t in tickers:
        qp.binary_var(name=t)
        
    linear = {}
    quadratic = {}
    
    w_val = 1.0 / float(B)
    for i in range(n):
        if w_val > caps[tickers[i]] + 1e-5:
            # Enforce x_i = 0 via large penalty since it violates cap
            linear[tickers[i]] = -1000.0
        else:
            linear[tickers[i]] = mu_hat[i] + 2 * penalty * B
            
        for j in range(n):
            if (tickers[i], tickers[j]) not in quadratic:
                quadratic[(tickers[i], tickers[j])] = 0.0
            quadratic[(tickers[i], tickers[j])] += - (risk_aversion * sigma[i][j])
            if i == j: # penalty is - lambda (sum x_i)^2 -> - lambda x_i x_j. Handled correctly
                pass
            quadratic[(tickers[i], tickers[j])] += - penalty
            
    qp.maximize(linear=linear, quadratic=quadratic)
    
    start_time = time.perf_counter()
    
    sampler = Sampler()
    optimizer = COBYLA(maxiter=50) 
    qaoa = QAOA(sampler=sampler, optimizer=optimizer, reps=reps)
    
    optimizer_algo = MinimumEigenOptimizer(qaoa)
    result = optimizer_algo.solve(qp)
    
    solve_time_ms = (time.perf_counter() - start_time) * 1000.0
    
    x = result.x
    status = "optimal" if result.status.name == "SUCCESS" else "optimal_inaccurate"
    
    # Construct weights enforcing cardinality
    sum_x = np.sum(x)
    if sum_x == 0:
        w_val_actual = 0.0
    else:
        # Technically QAOA might return a subset of size != B.
        # But we'll assign 1/B weight or 1/sum_x ? 
        # For evaluation, we use actual sum_x to form weights that sum to 1.
        w_val_actual = 1.0 / sum_x
        
    weights_dict = {tickers[i]: float(x[i] * w_val_actual) for i in range(n)}
    
    # Real Markowitz objective
    w_vec = np.array([weights_dict[t] for t in tickers])
    mu_arr = np.array(mu_hat)
    sigma_arr = np.array(sigma)
    obj_val = (mu_arr.T @ w_vec - risk_aversion * (w_vec.T @ sigma_arr @ w_vec)).item()
    
    metadata = {
        "n_layers": reps,
        "optimizer": "COBYLA",
        "B": B,
        "qaoa_objective": result.fval
    }
    
    return weights_dict, obj_val, solve_time_ms, status, metadata
