import os
import pandas as pd
from data_loader.parse_multitable_csv import parse_multitable_csv

def main() -> None:
    """
    Parses the daily returns from the multi-table CSV file, tidies it by 
    converting percentages to decimals, handling missing values, and writes 
    the result to data/processed/daily_returns.csv.
    """
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    daily_file = os.path.join(root_dir, "12_Industry_Portfolios_Daily.csv")
    out_file = os.path.join(root_dir, "data", "processed", "daily_returns.csv")
    
    # Parse the daily returns section
    section_header = "Average Value Weighted Returns -- Daily"
    df = parse_multitable_csv(daily_file, section_header)
    
    # Ensure column order
    expected_cols = ["NoDur", "Durbl", "Manuf", "Enrgy", "Chems", "BusEq", "Telcm", "Utils", "Shops", "Hlth", "Money", "Other"]
    df = df[expected_cols]
    
    # Drop rows with NaN
    df.dropna(inplace=True)
    
    # Convert from percentages to decimal fractions
    df = df / 100.0
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    
    # Write to CSV
    df.to_csv(out_file)
    print(f"Successfully built tidy returns at {out_file}")

if __name__ == "__main__":
    main()
