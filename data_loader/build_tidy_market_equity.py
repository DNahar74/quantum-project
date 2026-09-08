import os
import pandas as pd
from data_loader.parse_multitable_csv import parse_multitable_csv

def main() -> None:
    """
    Parses the market equity tables from the monthly CSV file, tidies it by
    multiplying firm sizes by number of firms, and writes the result to
    data/processed/market_equity_monthly.csv.
    """
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monthly_file = os.path.join(root_dir, "5_Industry_Portfolios.csv")
    out_file = os.path.join(root_dir, "data", "processed", "market_equity_monthly.csv")
    
    # Parse the firm size and number of firms sections
    size_header = "Average Firm Size"
    count_header = "Number of Firms in Portfolios"
    
    try:
        size_df = parse_multitable_csv(monthly_file, size_header)
        count_df = parse_multitable_csv(monthly_file, count_header)
    except FileNotFoundError:
        print(f"File {monthly_file} not found. Cannot build tidy market equity.")
        return
        
    expected_cols = ["Cnsmr", "Manuf", "HiTec", "Hlth", "Other"]
    size_df = size_df[expected_cols]
    count_df = count_df[expected_cols]
    
    # Align the two DataFrames by their index (month)
    # Market equity = average firm size * number of firms
    # Note: size_df values are in millions, but as long as we just need shares later, units don't matter much.
    # However, let's keep them as parsed. Element-wise multiplication.
    me_df = size_df.multiply(count_df, fill_value=0)
    
    # Drop rows where we have NaN or missing
    me_df.dropna(inplace=True)
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    
    # Write to CSV
    me_df.to_csv(out_file)
    print(f"Successfully built tidy market equity at {out_file}")

if __name__ == "__main__":
    main()
