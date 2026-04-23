"""
NASDAQ FTP provider — fetches official ticker universe.

Sources:
  - https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt  (NASDAQ)
  - https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt   (NYSE, AMEX, etc.)
"""

import logging
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

# Exchange codes from otherlisted.txt
EXCHANGE_MAP = {
    "N": "NYSE",
    "A": "AMEX",
    "P": "NYSE ARCA",
    "Z": "BATS",
    "V": "IEX",
}


def fetch_nasdaq_listed() -> pd.DataFrame:
    """Fetch NASDAQ-listed securities."""
    logger.info("Fetching NASDAQ listed securities...")
    resp = requests.get(NASDAQ_URL, timeout=30)
    resp.raise_for_status()
    # The file is pipe-delimited with a footer line
    lines = resp.text.strip().split("\n")
    # Remove footer (last line starts with "File Creation Time")
    data_lines = [line for line in lines if not line.startswith("File Creation Time")]
    df = pd.read_csv(StringIO("\n".join(data_lines)), sep="|")
    df = df.rename(columns={
        "Symbol": "symbol",
        "Security Name": "name",
        "Market Category": "market_category",
        "ETF": "is_etf",
        "Test Issue": "is_test",
        "Financial Status": "financial_status",
        "Round Lot Size": "round_lot",
        "NextShares": "is_nextshares",
    })
    df["exchange"] = "NASDAQ"
    return df


def fetch_other_listed() -> pd.DataFrame:
    """Fetch NYSE, AMEX, and other exchange securities."""
    logger.info("Fetching other listed securities...")
    resp = requests.get(OTHER_URL, timeout=30)
    resp.raise_for_status()
    lines = resp.text.strip().split("\n")
    data_lines = [line for line in lines if not line.startswith("File Creation Time")]
    df = pd.read_csv(StringIO("\n".join(data_lines)), sep="|")
    df = df.rename(columns={
        "ACT Symbol": "symbol",
        "Security Name": "name",
        "Exchange": "exchange_code",
        "ETF": "is_etf",
        "Test Issue": "is_test",
        "NASDAQ Symbol": "nasdaq_symbol",
    })
    df["exchange"] = df["exchange_code"].map(EXCHANGE_MAP).fillna("OTHER")
    return df


def fetch_full_universe(cache_path: str | None = None) -> pd.DataFrame:
    """
    Fetch complete US ticker universe from NASDAQ FTP.
    Returns DataFrame with columns: symbol, name, exchange, is_etf, is_test
    Filters out ETFs and test issues.
    """
    if cache_path and Path(cache_path).exists():
        cache = Path(cache_path)
        # Use cache if less than 24 hours old
        age_hours = (pd.Timestamp.now() - pd.Timestamp(cache.stat().st_mtime, unit="s")).total_seconds() / 3600
        if age_hours < 24:
            logger.info(f"Using cached universe ({cache_path}, {age_hours:.1f}h old)")
            return pd.read_parquet(cache_path)

    nasdaq = fetch_nasdaq_listed()
    other = fetch_other_listed()

    # Normalize columns
    cols = ["symbol", "name", "exchange", "is_etf", "is_test"]
    nasdaq_clean = nasdaq[[c for c in cols if c in nasdaq.columns]].copy()
    other_clean = other[[c for c in cols if c in other.columns]].copy()

    combined = pd.concat([nasdaq_clean, other_clean], ignore_index=True)

    # Normalize boolean columns
    combined["is_etf"] = combined["is_etf"].astype(str).str.upper() == "Y"
    combined["is_test"] = combined["is_test"].astype(str).str.upper() == "Y"

    # Filter out ETFs and test issues
    combined = combined[~combined["is_etf"] & ~combined["is_test"]]

    # Clean symbols
    combined["symbol"] = combined["symbol"].astype(str).str.strip()
    combined = combined[combined["symbol"].str.len() <= 5]  # Reasonable ticker length
    combined = combined.drop_duplicates(subset="symbol")

    logger.info(f"Universe: {len(combined)} active tickers ({combined['exchange'].value_counts().to_dict()})")

    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        combined.to_parquet(cache_path, index=False)
        logger.info(f"Cached to {cache_path}")

    return combined
