"""
Data ingestion pipeline — orchestrates universe fetch, OHLCV download, and classification.
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

from .providers import nasdaq_ftp, yfinance_provider, fmp_provider

logger = logging.getLogger(__name__)

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickers (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    exchange TEXT,
    country TEXT,
    type TEXT,
    universe TEXT,
    sector TEXT,
    industry TEXT,
    market_cap REAL,
    float_shares REAL,
    ipo_date TEXT,
    is_active INTEGER DEFAULT 1,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS daily_prices (
    symbol TEXT,
    date TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    dollar_volume REAL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS indicators (
    symbol TEXT,
    date TEXT,
    adr_pct_10 REAL,
    adr_pct_20 REAL,
    adr_pct_30 REAL,
    trend_intensity REAL,
    price_growth_5d REAL,
    price_growth_1m REAL,
    price_growth_3m REAL,
    price_growth_6m REAL,
    price_growth_1y REAL,
    price_growth_2y REAL,
    rank_5d REAL,
    rank_1m REAL,
    rank_3m REAL,
    rank_6m REAL,
    rank_1y REAL,
    rank_2y REAL,
    composite_score REAL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    auto_populate_scan TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS watchlist_items (
    watchlist_id INTEGER REFERENCES watchlists(id),
    symbol TEXT REFERENCES tickers(symbol),
    added_at TEXT,
    added_from_scan TEXT,
    notes TEXT,
    flagged INTEGER DEFAULT 0,
    PRIMARY KEY (watchlist_id, symbol)
);

CREATE TABLE IF NOT EXISTS scan_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT,
    run_date TEXT,
    symbol TEXT,
    score REAL,
    rank_in_scan INTEGER,
    snapshot TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type TEXT,
    symbol TEXT,
    message TEXT,
    triggered_at TEXT,
    delivered INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_prices_symbol ON daily_prices(symbol);
CREATE INDEX IF NOT EXISTS idx_prices_date ON daily_prices(date);
CREATE INDEX IF NOT EXISTS idx_indicators_date ON indicators(date);
CREATE INDEX IF NOT EXISTS idx_scan_results_scan ON scan_results(scan_id, run_date);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize SQLite database with schema."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(DB_SCHEMA)
    conn.commit()
    logger.info(f"Database initialized: {db_path}")
    return conn


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def update_universe(db_path: str, cache_path: str = "data/universe.parquet") -> pd.DataFrame:
    """Step 1: Fetch and classify the full ticker universe."""
    logger.info("=== Updating ticker universe ===")

    # Fetch from NASDAQ FTP
    universe = nasdaq_ftp.fetch_full_universe(cache_path=cache_path)

    # Classify and save to DB
    classified = fmp_provider.classify_tickers(universe, db_path)

    return classified


def update_ohlcv(db_path: str, tickers: list[str] | None = None, full: bool = False) -> int:
    """Step 2: Download/update OHLCV data."""
    logger.info("=== Updating OHLCV data ===")

    conn = get_connection(db_path)

    if tickers is None:
        # Get active tickers from DB
        result = pd.read_sql("SELECT symbol FROM tickers WHERE is_active=1", conn)
        tickers = result["symbol"].tolist()

    conn.close()

    if not tickers:
        logger.warning("No tickers to download")
        return 0

    if full:
        return yfinance_provider.download_all(tickers, db_path)
    else:
        return yfinance_provider.incremental_update(tickers, db_path)


def get_prices(db_path: str, symbols: list[str] | None = None, days: int = 550) -> pd.DataFrame:
    """
    Load OHLCV data from DB into a DataFrame.
    Returns wide-format DataFrame: index=date, columns=symbol, values=close (or specified field).
    """
    conn = get_connection(db_path)

    query = """
        SELECT symbol, date, open, high, low, close, volume, dollar_volume
        FROM daily_prices
        WHERE date >= date('now', ?)
        ORDER BY date
    """
    df = pd.read_sql(query, conn, params=(f"-{days} days",))
    conn.close()

    if symbols:
        df = df[df["symbol"].isin(symbols)]

    return df


def get_close_wide(db_path: str, symbols: list[str] | None = None, days: int = 550) -> pd.DataFrame:
    """Get close prices in wide format (date × symbol) for ranking calculations."""
    df = get_prices(db_path, symbols, days)
    if df.empty:
        return pd.DataFrame()
    pivot = df.pivot_table(index="date", columns="symbol", values="close")
    return pivot


def get_universe_symbols(db_path: str, universe: str = "all") -> list[str]:
    """Get list of symbols for a given universe."""
    conn = get_connection(db_path)

    if universe == "all":
        query = "SELECT symbol FROM tickers WHERE is_active=1"
        params = ()
    else:
        query = "SELECT symbol FROM tickers WHERE is_active=1 AND universe=?"
        params = (universe,)

    result = pd.read_sql(query, conn, params=params)
    conn.close()
    return result["symbol"].tolist()
