import os
import pandas as pd
import numpy as np
import pytest
from tempfile import NamedTemporaryFile
from data_loader.parse_multitable_csv import parse_multitable_csv
from data_loader.build_tidy_returns import build_tidy_returns
from data_loader.lookup import sigma_for_date, caps_for_date

# Column order build_tidy_returns writes from 12_Industry_Portfolios_Daily.csv.
INDUSTRIES = ["NoDur", "Durbl", "Manuf", "Enrgy", "Chems", "BusEq", "Telcm", "Utils", "Shops", "Hlth", "Money", "Other"]

FIXTURE_CSV = """
This is some dummy text.

  Section 1
,Cnsmr,Manuf,HiTec,Hlth,Other
192607, 1.0, 2.0, 3.0, 4.0, 5.0
192608, -99.99, 2.0, 3.0, 4.0, 5.0

  Section 2
,Cnsmr,Manuf,HiTec,Hlth,Other
19260701, 10.0, 20.0, 30.0, 40.0, 50.0
19260702, 11.0, 21.0, 31.0, 41.0, 51.0
"""

def test_parse_multitable_csv():
    with NamedTemporaryFile(mode="w", delete=False, suffix=".csv") as f:
        f.write(FIXTURE_CSV)
        f.flush()
        file_path = f.name
        
    try:
        df_sec1 = parse_multitable_csv(file_path, "Section 1")
        assert len(df_sec1) == 2
        assert "Cnsmr" in df_sec1.columns
        assert pd.isna(df_sec1.loc["1926-08", "Cnsmr"])
        
        df_sec2 = parse_multitable_csv(file_path, "Section 2")
        assert len(df_sec2) == 2
        assert df_sec2.loc["1926-07-01", "Cnsmr"] == 10.0
    finally:
        os.remove(file_path)

def test_build_tidy_returns_output():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    daily_returns_path = os.path.join(root_dir, "data", "processed", "daily_returns.csv")
    
    if not os.path.exists(daily_returns_path):
        pytest.skip("daily_returns.csv not found")
        
    df = pd.read_csv(daily_returns_path, index_col="date")
    
    # Check column order
    assert list(df.columns) == INDUSTRIES
    
    # Check for NaNs
    assert not df.isna().any().any()
    
    # Check if values are in decimal form (max should be much less than 100, typically < 1)
    # Even huge daily returns won't exceed 1.0 (100%), except maybe extreme outliers,
    # but the mean absolute value should be small.
    assert df.abs().max().max() < 10.0

def test_sigma_for_date_properties():
    try:
        # 1926-07-01 is start, 252 days later is approx mid 1927
        sigma = sigma_for_date("1927-07-01", window_days=252)
        
        # Check symmetric
        np.testing.assert_allclose(sigma.values, sigma.values.T, atol=1e-8)
        
        # Check positive semi-definite
        eigenvalues = np.linalg.eigvalsh(sigma.values)
        assert np.all(eigenvalues >= -1e-8)
        
        assert sigma.shape == (len(INDUSTRIES), len(INDUSTRIES))
    except Exception as e:
        if isinstance(e, FileNotFoundError):
            pytest.skip("Data not generated yet")
        raise e

def test_caps_for_date_sanity():
    try:
        date = "2020-01-01"
        sigma = sigma_for_date(date, window_days=252)
        caps = caps_for_date(date, window_days=252)
        
        assert isinstance(caps, dict)
        
        # Check that highest volatility gets lowest cap
        vols = np.sqrt(np.diag(sigma))
        vol_dict = dict(zip(sigma.columns, vols))
        
        highest_vol_asset = max(vol_dict, key=vol_dict.get)
        lowest_vol_asset = min(vol_dict, key=vol_dict.get)
        
        # Volatilities are different
        assert vol_dict[highest_vol_asset] > vol_dict[lowest_vol_asset]
        
        # Therefore caps should be inversely related (if not strictly clipped to the same ceiling)
        # Check that the highest vol asset has a smaller or equal cap than the lowest vol asset
        assert caps[highest_vol_asset] < caps[lowest_vol_asset]
        
    except Exception as e:
        if isinstance(e, FileNotFoundError):
            pytest.skip("Data not generated yet")
        else:
             raise e

def test_any_industry_file_flows_through_build_and_lookup(tmp_path, monkeypatch):
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_file = str(tmp_path / "daily_returns_5_industry.csv")

    df = build_tidy_returns(os.path.join(root_dir, "5_Industry_Portfolios_Daily.csv"), out_file)

    assert list(df.columns) == ["Cnsmr", "Manuf", "HiTec", "Hlth", "Other"]
    assert not df.isna().any().any()
    assert df.abs().max().max() < 1.0      # decimals, not percent

    # sigma/caps follow RETURNS_FILE, the same file the orchestrator reads realized returns from.
    monkeypatch.setenv("RETURNS_FILE", out_file)
    sigma = sigma_for_date("2020-01-03", window_days=252)
    caps = caps_for_date("2020-01-03", window_days=252)
    assert sigma.shape == (5, 5)
    assert list(caps) == list(df.columns)

def test_sigma_for_date_too_early():
    with pytest.raises(ValueError):
        # 1926-07-01 is the start of the dataset, window_days=252 will fail
        sigma_for_date("1926-07-01", window_days=252)
