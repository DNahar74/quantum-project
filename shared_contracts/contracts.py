from pydantic import BaseModel
from typing import Dict, List

class OptimizationRequest(BaseModel):
    tickers: List[str]            # ["Cnsmr","Manuf","HiTec","Hlth","Other"]
    mu_hat: List[float]
    sigma: List[List[float]]
    risk_aversion: float          # q — identical across every optimizer arm for a given run
    caps: Dict[str, float]        # per-asset max weight, from market-equity share
    long_only: bool = True
    request_id: str               # ties back to the exact mu_hat/sigma/q version used

class OptimizationResult(BaseModel):
    request_id: str
    weights: Dict[str, float]
    objective_value: float
    solve_time_ms: float
    solver_status: str
    solver_name: str
