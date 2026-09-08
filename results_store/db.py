import sqlite3
import hashlib
import json
import numpy as np
from typing import Dict, Any, List

def init_db(db_path: str = "results.db"):
    # Justification for SQLite: For a 5-asset, weekly rebalanced backtest over historical data,
    # the total row count is on the order of a few thousand rows. SQLite easily handles this
    # locally without the operational overhead of a dedicated Postgres container, while still
    # supporting JSON types and ACID guarantees needed for this project.
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            rebalance_date TEXT NOT NULL,
            arm_name TEXT NOT NULL,
            weights TEXT NOT NULL, -- JSON
            turnover REAL NOT NULL,
            realized_return REAL NOT NULL,
            transaction_cost REAL NOT NULL,
            solver_status TEXT NOT NULL,
            solve_time_ms REAL NOT NULL,
            sigma_hash TEXT NOT NULL,
            caps_hash TEXT NOT NULL,
            risk_aversion REAL NOT NULL,
            UNIQUE(rebalance_date, arm_name)
        )
    ''')
    conn.commit()
    conn.close()

def compute_hash(data: Any) -> str:
    """
    Computes a stable SHA-256 hash for arrays/dicts.
    """
    if isinstance(data, (np.ndarray, list)):
        data_str = json.dumps(np.array(data).tolist(), sort_keys=True)
    elif isinstance(data, dict):
        data_str = json.dumps(data, sort_keys=True)
    else:
        data_str = str(data)
    return hashlib.sha256(data_str.encode('utf-8')).hexdigest()

def insert_result(db_path: str, result: Dict[str, Any]):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO backtest_results (
            request_id, rebalance_date, arm_name, weights, turnover,
            realized_return, transaction_cost, solver_status,
            solve_time_ms, sigma_hash, caps_hash, risk_aversion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        result["request_id"],
        result["rebalance_date"],
        result["arm_name"],
        json.dumps(result["weights"]),
        result["turnover"],
        result["realized_return"],
        result["transaction_cost"],
        result["solver_status"],
        result["solve_time_ms"],
        result["sigma_hash"],
        result["caps_hash"],
        result["risk_aversion"]
    ))
    conn.commit()
    conn.close()
