"""
FMP (Financial Modeling Prep) free-tier provider.

Free tier: 250 requests/day. Used for:
  - Stock profile (sector, industry, country, market cap, IPO date)
  - IPO calendar (1 request per year range)

Classification logic:
  - ADR: exchange IN (NYSE, NASDAQ, AMEX) AND country != "US"
  - OTC: exchange IN (OTC, PINK, OTCQB, OTCQX)
"""

import logging
import os
import time
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://financialmodelingprep.com/api/v3"


def _get_key() -> str:
    key = os.environ.get("MOMO_FMP_KEY", "")
    if not key:
        logger.warning("MOMO_FMP_KEY not set — FMP features disabled")
    return key


def fetch_profile(symbol: str) -> dict | None:
    """Fetch stock profile for a single ticker."""
    key = _get_key()
    if not key:
        return None

    try:
        resp = requests.get(
            f"{BASE_URL}/profile/{symbol}",
            params={"apikey": key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        logger.warning(f"FMP profile failed for {symbol}: {e}")
        return None


def fetch_profiles_batch(symbols: list[str], daily_limit: int = 250) -> pd.DataFrame:
    """
    Fetch profiles for a batch of symbols. Respects daily rate limit.
    Returns DataFrame with classification data.
    """
    key = _get_key()
    if not key:
        return pd.DataFrame()

    results = []
    count = 0

    for symbol in symbols:
        if count >= daily_limit:
            logger.info(f"FMP daily limit reached ({daily_limit}). Stopping.")
            break

        profile = fetch_profile(symbol)
        if profile:
            results.append({
                "symbol": symbol,
                "name": profile.get("companyName", ""),
                "exchange": profile.get("exchangeShortName", ""),
                "country": profile.get("country", ""),
                "sector": profile.get("sector", ""),
                "industry": profile.get("industry", ""),
                "market_cap": profile.get("mktCap", 0),
                "ipo_date": profile.get("ipoDate", ""),
                "is_adr": profile.get("country", "US") != "US",
            })
        count += 1
        time.sleep(0.5)  # Be nice to free tier

    if results:
        df = pd.DataFrame(results)
        # Classify universe
        df["universe"] = "us_listed"
        df.loc[df["is_adr"], "universe"] = "adr"
        # Micro/Small cap classification
        df["cap_class"] = pd.cut(
            df["market_cap"],
            bins=[0, 300_000_000, 2_000_000_000, float("inf")],
            labels=["micro", "small", "mid_large"],
        )
        return df
    return pd.DataFrame()


def fetch_ipo_calendar(year: int) -> pd.DataFrame:
    """Fetch IPO calendar for a given year. 1 request total."""
    key = _get_key()
    if not key:
        return pd.DataFrame()

    try:
        resp = requests.get(
            f"{BASE_URL}/ipo_calendar",
            params={"apikey": key, "from": f"{year}-01-01", "to": f"{year}-12-31"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception as e:
        logger.warning(f"FMP IPO calendar failed: {e}")
        return pd.DataFrame()


def classify_tickers(tickers_df: pd.DataFrame, db_path: str) -> pd.DataFrame:
    """
    Classify tickers into universes using NASDAQ exchange data + optional FMP.
    Saves results to SQLite tickers table.
    """
    import sqlite3

    df = tickers_df.copy()

    # Basic classification from exchange
    df["universe"] = "us_listed"
    df.loc[df["exchange"] == "NASDAQ", "universe"] = "us_listed"
    df.loc[df["exchange"] == "NYSE", "universe"] = "us_listed"
    df.loc[df["exchange"] == "AMEX", "universe"] = "us_listed"
    df.loc[df["exchange"] == "NYSE ARCA", "universe"] = "us_listed"
    # OTC detection (symbols with 5 chars ending in F or Y are often OTC)
    otc_mask = (
        (df["exchange"].isin(["OTC", "OTHER"]))
        | (df["symbol"].str.len() == 5)
    )
    df.loc[otc_mask, "universe"] = "otc"

    # Save to DB
    conn = sqlite3.connect(db_path)
    save_df = df[["symbol", "name", "exchange", "universe"]].copy()
    save_df["is_active"] = 1
    save_df["updated_at"] = str(pd.Timestamp.now())
    save_df.to_sql("tickers", conn, if_exists="replace", index=False)
    conn.close()

    logger.info(f"Classified {len(df)} tickers: {df['universe'].value_counts().to_dict()}")
    return df
