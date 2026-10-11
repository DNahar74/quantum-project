import json
import sqlite3

import pytest
import numpy as np
import pandas as pd
import httpx
import respx
from unittest.mock import patch

from backtest_orchestrator.orchestrator import compute_realized_return, send_optimization_request, run_backtest, resolve_backtest_bounds
from backtest_orchestrator import orchestrator
from backtest_orchestrator.forecaster import get_mu_hat, MuHatUnavailableError, MU_HAT_HORIZON_DAYS
from results_store.db import compute_hash
from shared_contracts.contracts import OptimizationRequest

def test_resolve_backtest_bounds_uses_full_historical_window():
    dates = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    returns_df = pd.DataFrame({"A": np.linspace(0.0, 0.02, len(dates))}, index=dates)

    start, end = resolve_backtest_bounds(returns_df, None, None, 252)

    # Full history by default; run_backtest skips early weeks that lack a full lookback window.
    assert start == pd.Timestamp("2020-01-01")
    assert end == pd.Timestamp("2021-12-31")

    # Explicit bounds outside the data are clamped to it.
    start, end = resolve_backtest_bounds(returns_df, "2019-06-01", "2022-06-01", 252)
    assert (start, end) == (pd.Timestamp("2020-01-01"), pd.Timestamp("2021-12-31"))


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


def _write_mu_hat(tmp_path, monkeypatch):
    table = pd.DataFrame(
        {"A": [0.01, 0.02], "B": [-0.01, 0.03]},
        index=pd.DatetimeIndex(["2024-01-05", "2024-01-12"], name="date"),
    )
    path = tmp_path / "mu_hat.csv"
    table.to_csv(path)
    monkeypatch.setenv("MU_HAT_FILE", str(path))


def test_get_mu_hat_reads_row_in_ticker_order(tmp_path, monkeypatch):
    _write_mu_hat(tmp_path, monkeypatch)

    assert get_mu_hat("2024-01-12", ["B", "A"]) == [0.03, 0.02]


def test_get_mu_hat_raises_for_missing_date_or_ticker(tmp_path, monkeypatch):
    _write_mu_hat(tmp_path, monkeypatch)

    with pytest.raises(MuHatUnavailableError):
        get_mu_hat("2024-01-19", ["A", "B"])
    with pytest.raises(ValueError):
        get_mu_hat("2024-01-05", ["A", "C"])


def test_sigma_scaled_to_forecaster_horizon():
    from forecaster.config import DATA

    assert MU_HAT_HORIZON_DAYS == DATA.horizon


@respx.mock
def test_run_backtest_sends_weekly_sigma_and_records_mu_hat_hash(tmp_path, monkeypatch):
    dates = pd.bdate_range("2024-01-01", "2024-01-31")
    returns_file = tmp_path / "returns.csv"
    pd.DataFrame({"A": 0.001, "B": 0.002}, index=pd.DatetimeIndex(dates, name="date")).to_csv(returns_file)
    db_path = tmp_path / "results.db"
    monkeypatch.setenv("RETURNS_FILE", str(returns_file))
    monkeypatch.setenv("DB_PATH", str(db_path))

    daily_sigma = pd.DataFrame([[0.0001, 0.00002], [0.00002, 0.0004]], index=["A", "B"], columns=["A", "B"])
    monkeypatch.setattr(orchestrator, "sigma_for_date", lambda date, window: daily_sigma)
    monkeypatch.setattr(orchestrator, "caps_for_date", lambda date, window: {"A": 1.0, "B": 1.0})
    monkeypatch.setattr(orchestrator, "get_mu_hat", lambda date, tickers: [0.01, 0.02])

    result = {"weights": {"A": 0.5, "B": 0.5}, "objective_value": 0.0, "solve_time_ms": 1.0,
              "solver_status": "optimal", "solver_name": "test"}
    routes = [
        respx.post(url).mock(side_effect=lambda request: httpx.Response(
            200, json={**result, "request_id": json.loads(request.content)["request_id"]}))
        for url in ("http://localhost:8000/optimize", "http://localhost:8001/optimize")
    ]

    df = run_backtest()

    for route in routes:
        for call in route.calls:
            sent = json.loads(call.request.content)
            np.testing.assert_allclose(sent["sigma"], (daily_sigma * MU_HAT_HORIZON_DAYS).values)
    with sqlite3.connect(db_path) as conn:
        hashes = {row[0] for row in conn.execute("SELECT mu_hat_hash FROM backtest_results")}
    assert len(df) == 2 * len(routes[0].calls) > 0
    assert hashes == {compute_hash([0.01, 0.02])}
