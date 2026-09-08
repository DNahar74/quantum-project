import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient
from app.main import app
import numpy as np

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_optimize_success():
    req = {
        "tickers": ["A", "B", "C"],
        "mu_hat": [0.10, 0.05, 0.1],
        "sigma": [[0.04, 0.0, 0.0], [0.0, 0.01, 0.0], [0.0, 0.0, 0.02]],
        "risk_aversion": 1.0,
        "caps": {"A": 1.0, "B": 1.0, "C": 1.0},
        "long_only": True,
        "request_id": "test-req"
    }
    response = client.post("/optimize", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "test-req"
    assert "solve_time_ms" in data
    assert data["solver_status"] in ["optimal", "optimal_inaccurate"]
    assert data["solver_name"] == "qiskit_qaoa"

def test_optimize_malformed_sigma_shape():
    req = {
        "tickers": ["A", "B"],
        "mu_hat": [0.10, 0.05],
        "sigma": [[0.04, 0.0]], # Not n x n
        "risk_aversion": 1.0,
        "caps": {"A": 1.0, "B": 1.0},
        "long_only": True,
        "request_id": "test-req"
    }
    response = client.post("/optimize", json=req)
    assert response.status_code == 422

def test_optimize_malformed_sigma_asymmetric():
    req = {
        "tickers": ["A", "B"],
        "mu_hat": [0.10, 0.05],
        "sigma": [[0.04, 0.05], [0.01, 0.01]], # Asymmetric
        "risk_aversion": 1.0,
        "caps": {"A": 1.0, "B": 1.0},
        "long_only": True,
        "request_id": "test-req"
    }
    response = client.post("/optimize", json=req)
    assert response.status_code == 422

def test_optimize_nan_in_sigma():
    req = {
        "tickers": ["A", "B"],
        "mu_hat": [0.10, 0.05],
        "sigma": [[0.04, "NaN"], ["NaN", 0.01]],
        "risk_aversion": 1.0,
        "caps": {"A": 1.0, "B": 1.0},
        "long_only": True,
        "request_id": "test-req"
    }
    response = client.post("/optimize", json=req)
    assert response.status_code == 422
