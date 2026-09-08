import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "results_api"))
from fastapi.testclient import TestClient
from app.main import app

def run_demo():
    client = TestClient(app)
    
    # Let's hit the runs endpoint
    runs_res = client.get("/runs")
    print("GET /runs")
    print(json.dumps(runs_res.json(), indent=2))
    print("-" * 40)
    
    # Let's hit the comparison endpoint
    comp_res = client.get("/comparison")
    print("GET /comparison")
    print(json.dumps(comp_res.json(), indent=2))
    print("-" * 40)
    
    # Hit the results endpoint (first 2 records)
    res = client.get("/results")
    data = res.json()
    print("GET /results (First 2 records)")
    print(json.dumps(data[:2], indent=2))
    
if __name__ == "__main__":
    run_demo()
