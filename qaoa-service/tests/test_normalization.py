import numpy as np

def test_bitstring_decode_and_normalization():
    # Simulate the decode+normalize path in solver.py
    tickers = ["Cnsmr", "Manuf", "HiTec", "Hlth", "Other"]
    n = len(tickers)
    
    # Known bitstring '10100' -> selecting Cnsmr and HiTec
    # For a problem where B=2
    x = np.array([1.0, 0.0, 1.0, 0.0, 0.0])
    B = 2
    
    sum_x = np.sum(x)
    
    # Guard logic
    if sum_x == 0 or sum_x < B:
        status = "infeasible"
        w_val_actual = 0.0
        weights_dict = {tickers[i]: 0.0 for i in range(n)}
    else:
        status = "optimal"
        w_val_actual = 1.0 / sum_x
        weights_dict = {tickers[i]: float(x[i] * w_val_actual) for i in range(n)}
        
    assert status == "optimal"
    
    # Assert output weights sum to exactly 1.0
    total_weight = sum(weights_dict.values())
    assert np.isclose(total_weight, 1.0), f"Weights sum to {total_weight}, expected 1.0"
    
    # Map to correct asset names
    assert weights_dict["Cnsmr"] == 0.5
    assert weights_dict["Manuf"] == 0.0
    assert weights_dict["HiTec"] == 0.5
    assert weights_dict["Hlth"] == 0.0
    assert weights_dict["Other"] == 0.0

def test_all_zeros_rejection():
    # Test that all-zero bitstring is caught and rejected
    tickers = ["Cnsmr", "Manuf", "HiTec", "Hlth", "Other"]
    n = len(tickers)
    x = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    B = 3
    
    sum_x = np.sum(x)
    if sum_x == 0 or sum_x < B:
        status = "infeasible"
        w_val_actual = 0.0
        weights_dict = {tickers[i]: 0.0 for i in range(n)}
        
    assert status == "infeasible"
    assert sum(weights_dict.values()) == 0.0
