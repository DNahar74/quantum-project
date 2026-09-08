import sys
import os
import math
import numpy as np

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared_contracts.contracts import OptimizationRequest, OptimizationResult
from app.solver import solve_markowitz

app = FastAPI(title="Markowitz Service")

# Setup metrics
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/optimize", response_model=OptimizationResult)
def optimize(req: OptimizationRequest):
    # Validation at API boundary
    n = len(req.tickers)
    
    if len(req.mu_hat) != n:
        raise HTTPException(status_code=422, detail="mu_hat length must match tickers length")
        
    if len(req.sigma) != n:
        raise HTTPException(status_code=422, detail="sigma must be an n x n matrix")
        
    for row in req.sigma:
        if len(row) != n:
            raise HTTPException(status_code=422, detail="sigma must be an n x n matrix")
            
    # Check NaN and infinity
    for val in req.mu_hat:
        if math.isnan(val) or math.isinf(val):
            raise HTTPException(status_code=422, detail="mu_hat contains NaN or inf")
            
    for row in req.sigma:
        for val in row:
            if math.isnan(val) or math.isinf(val):
                raise HTTPException(status_code=422, detail="sigma contains NaN or inf")
                
    # Check symmetric (within tolerance)
    sigma_arr = np.array(req.sigma, dtype=float)
    if not np.allclose(sigma_arr, sigma_arr.T, atol=1e-5):
        raise HTTPException(status_code=422, detail="sigma is not symmetric")
        
    # Check caps match tickers
    for t in req.tickers:
        if t not in req.caps:
            raise HTTPException(status_code=422, detail=f"caps missing for ticker {t}")

    # Solve
    try:
        weights, obj_val, solve_time_ms, solver_status = solve_markowitz(
            tickers=req.tickers,
            mu_hat=req.mu_hat,
            sigma=req.sigma,
            risk_aversion=req.risk_aversion,
            caps=req.caps,
            long_only=req.long_only
        )
    except Exception as e:
        # Unexpected error (should not happen in normal conditions)
        raise HTTPException(status_code=500, detail=str(e))
        
    return OptimizationResult(
        request_id=req.request_id,
        weights=weights,
        objective_value=obj_val,
        solve_time_ms=solve_time_ms,
        solver_status=solver_status,
        solver_name="cvxpy_osqp"
    )
