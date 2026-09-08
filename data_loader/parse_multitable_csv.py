import pandas as pd
import io

def parse_multitable_csv(file_path: str, section_header: str) -> pd.DataFrame:
    """
    Parses a specific section from a multi-table CSV file, common in Fama-French datasets.
    
    Args:
        file_path: Path to the CSV file.
        section_header: The exact text (ignoring leading/trailing whitespace) of the section's header.
        
    Returns:
        A pandas DataFrame containing the parsed section, with a DatetimeIndex or PeriodIndex.
    """
    lines = []
    in_section = False
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            
            if not in_section:
                # Check if we found the section header
                if stripped == section_header.strip():
                    in_section = True
                continue
            
            # We are in the section.
            # If we hit a completely empty line after reading some data, the section is over.
            if not stripped:
                if len(lines) > 0:
                    break
                else:
                    continue
            
            lines.append(line)
            
    if not lines:
        raise ValueError(f"Section '{section_header}' not found or empty in {file_path}")
        
    # Read the section into a DataFrame
    # The first line should be the column headers.
    csv_io = io.StringIO("".join(lines))
    df = pd.read_csv(csv_io, na_values=["-99.99", "-999", "-99.99", "-999.0", "-999.00"])
    
    # The first column is usually unnamed and contains the date.
    date_col = df.columns[0]
    df.rename(columns={date_col: "date"}, inplace=True)
    
    # Parse the index. We have YYYYMMDD (length 8) or YYYYMM (length 6) or YYYY (length 4)
    # Fama French dates are usually integers.
    df["date"] = df["date"].astype(str).str.strip()
    
    # Drop rows where date doesn't look like a valid date integer
    df = df[df["date"].str.match(r"^\d{6,8}$")]
    
    # Determine frequency based on string length of first valid date
    if len(df["date"].iloc[0]) == 8:
        # Daily
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
        df.set_index("date", inplace=True)
    elif len(df["date"].iloc[0]) == 6:
        # Monthly
        df["date"] = pd.to_datetime(df["date"], format="%Y%m").dt.to_period("M")
        df.set_index("date", inplace=True)
    else:
        # Fallback
        df.set_index("date", inplace=True)
        
    # Convert all columns except index to numeric, just in case
    df = df.apply(pd.to_numeric, errors='coerce')
    
    # Ensure column names don't have leading/trailing whitespace
    df.columns = df.columns.str.strip()
    
    return df
