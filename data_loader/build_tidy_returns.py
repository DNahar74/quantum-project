import os
import pandas as pd
from data_loader.parse_multitable_csv import parse_multitable_csv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RAW_FILE = os.path.join(ROOT_DIR, "12_Industry_Portfolios_Daily.csv")
DEFAULT_OUT_FILE = os.path.join(ROOT_DIR, "data", "processed", "daily_returns.csv")


def build_tidy_returns(raw_file: str, out_file: str) -> pd.DataFrame:
    """
    Parses the daily value-weighted returns from a Fama-French industry portfolio file
    (any number of industries, columns in file order), tidies it by converting
    percentages to decimals and dropping rows with missing values, and writes it to out_file.
    """
    # Parse the daily returns section
    section_header = "Average Value Weighted Returns -- Daily"
    df = parse_multitable_csv(raw_file, section_header)

    # Drop rows with NaN
    df.dropna(inplace=True)

    # Convert from percentages to decimal fractions
    df = df / 100.0

    # Ensure output directory exists
    os.makedirs(os.path.dirname(out_file), exist_ok=True)

    # Write to CSV
    df.to_csv(out_file)
    return df


def main() -> None:
    """Builds the processed returns file; RAW_RETURNS_FILE and RETURNS_FILE override the defaults."""
    raw_file = os.environ.get("RAW_RETURNS_FILE", DEFAULT_RAW_FILE)
    out_file = os.environ.get("RETURNS_FILE", DEFAULT_OUT_FILE)
    df = build_tidy_returns(raw_file, out_file)
    print(f"Successfully built tidy returns at {out_file} from {os.path.basename(raw_file)}: "
          f"{len(df.columns)} industries ({', '.join(df.columns)}), {len(df)} days")

if __name__ == "__main__":
    main()
