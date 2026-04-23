"""
Scan engine — executes configured scans against market data.
"""

import json
import logging
from datetime import datetime

import pandas as pd

from .filters import FilterChain
from .loader import build_filters, load_all_scans
from ..indicators import adr_percent, trend_intensity, price_rank
from ..scoring.composite import calculate_composite_score

logger = logging.getLogger(__name__)


def build_indicator_table(db_path: str) -> pd.DataFrame:
    """
    Build a complete indicator table for all symbols.
    This is the main data prep step before running scans.

    Returns DataFrame with columns:
        symbol, close, volume, dollar_volume, avg_volume,
        adr_pct_10, adr_pct_20, adr_pct_30,
        trend_intensity,
        growth_5d, growth_1m, growth_3m, growth_6m, growth_1y, growth_2y,
        rank_5d, rank_1m, rank_3m, rank_6m, rank_1y, rank_2y
    """
    from ..data.ingest import get_prices, get_close_wide, get_connection

    logger.info("Building indicator table...")

    # Load prices
    prices_df = get_prices(db_path, days=550)
    if prices_df.empty:
        logger.error("No price data in database")
        return pd.DataFrame()

    # Latest date per symbol
    latest = prices_df.sort_values("date").groupby("symbol").last().reset_index()

    # Calculate ADR%
    adr_result = adr_percent.adr_percent_bulk(prices_df)
    if not adr_result.empty:
        adr_latest = adr_result.sort_values("date").groupby("symbol").last().reset_index()
        adr_cols = [c for c in adr_latest.columns if c.startswith("adr_pct_")]
        latest = latest.merge(adr_latest[["symbol"] + adr_cols], on="symbol", how="left")

    # Calculate Trend Intensity
    ti_result = trend_intensity.trend_intensity_bulk(prices_df)
    if not ti_result.empty:
        ti_latest = ti_result.sort_values("date").groupby("symbol").last().reset_index()
        latest = latest.merge(ti_latest[["symbol", "trend_intensity"]], on="symbol", how="left")

    # Calculate price growth and ranks
    close_wide = get_close_wide(db_path, days=550)
    if not close_wide.empty:
        rank_result = price_rank.price_growth_bulk(prices_df, close_wide)
        if not rank_result.empty:
            latest = latest.merge(rank_result, on="symbol", how="left")

    # Calculate average volume (20-day)
    vol_avg = prices_df.groupby("symbol")["volume"].apply(
        lambda x: x.tail(20).mean()
    ).reset_index()
    vol_avg.columns = ["symbol", "avg_volume"]
    latest = latest.merge(vol_avg, on="symbol", how="left")

    # Calculate SMA20 (for extension filter)
    sma20 = prices_df.groupby("symbol")["close"].apply(
        lambda x: x.tail(20).mean()
    ).reset_index()
    sma20.columns = ["symbol", "sma_20"]
    latest = latest.merge(sma20, on="symbol", how="left")

    # Get universe classification
    conn = get_connection(db_path)
    try:
        tickers_df = pd.read_sql("SELECT symbol, universe, sector, industry FROM tickers", conn)
    except Exception:
        tickers_df = pd.read_sql("SELECT symbol, universe FROM tickers", conn)
    conn.close()
    latest = latest.merge(tickers_df, on="symbol", how="left")

    logger.info(f"Indicator table built: {len(latest)} symbols")
    return latest


def run_scan(scan_config: dict, indicator_table: pd.DataFrame, db_path: str) -> pd.DataFrame:
    """
    Execute a single scan against the indicator table.

    Returns filtered and scored DataFrame.
    """
    scan_info = scan_config["scan"]
    scan_id = scan_info["id"]
    scan_name = scan_info["name"]

    logger.info(f"Running scan: {scan_name} ({scan_id})")

    # Build filter chain
    filters = build_filters(scan_config)
    chain = FilterChain(filters)

    # Execute filters
    results = chain.execute(indicator_table.copy())

    if results.empty:
        logger.info(f"Scan {scan_name}: 0 results")
        return results

    # Apply scoring if enabled
    scoring_cfg = scan_config.get("scoring", {})
    if scoring_cfg.get("enabled", False):
        results = calculate_composite_score(results, scoring_cfg)

    # Sort by configured column
    display_cfg = scan_config.get("display", {})
    sort_by = display_cfg.get("sort_by", "composite_score")
    sort_order = display_cfg.get("sort_order", "desc")

    if sort_by in results.columns:
        results = results.sort_values(sort_by, ascending=(sort_order == "asc"))

    # Add scan metadata
    results["scan_id"] = scan_id
    results["scan_name"] = scan_name
    results["run_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    logger.info(f"Scan {scan_name}: {len(results)} results")
    return results


def run_all_scans(
    db_path: str,
    config_dir: str = "config/scans",
    indicator_table: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Run all enabled scans and return results dict.

    Returns: {scan_id: DataFrame of results}
    """
    # Load all scan configs
    scans = load_all_scans(config_dir)

    # Build indicator table once
    if indicator_table is None:
        indicator_table = build_indicator_table(db_path)

    if indicator_table.empty:
        logger.error("Empty indicator table — cannot run scans")
        return {}

    all_results = {}

    for scan_config in scans:
        if not scan_config["scan"].get("enabled", True):
            logger.info(f"Skipping disabled scan: {scan_config['scan']['name']}")
            continue

        results = run_scan(scan_config, indicator_table, db_path)
        if not results.empty:
            all_results[scan_config["scan"]["id"]] = results

            # Save to DB
            save_scan_results(db_path, scan_config["scan"]["id"], results)

    return all_results


def save_scan_results(db_path: str, scan_id: str, results: pd.DataFrame):
    """Save scan results to SQLite for history tracking."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    records = []
    for rank, (_, row) in enumerate(results.iterrows(), 1):
        # Snapshot key indicators as JSON
        snapshot = {}
        for col in ["close", "volume", "adr_pct_20", "trend_intensity", "composite_score"]:
            if col in row and pd.notna(row[col]):
                snapshot[col] = float(row[col])

        records.append({
            "scan_id": scan_id,
            "run_date": now,
            "symbol": row["symbol"],
            "score": row.get("composite_score", None),
            "rank_in_scan": rank,
            "snapshot": json.dumps(snapshot),
            "created_at": now,
        })

    if records:
        df = pd.DataFrame(records)
        df.to_sql("scan_results", conn, if_exists="append", index=False)

    conn.close()
    logger.info(f"Saved {len(records)} results for scan {scan_id}")


def format_results_table(results: pd.DataFrame, scan_config: dict, max_rows: int = 20) -> str:
    """Format scan results as a readable text table."""
    display_cfg = scan_config.get("display", {})
    fields = display_cfg.get("fields", [])

    if not fields:
        fields = ["symbol", "close", "volume"]

    # Filter to available columns
    available = [f for f in fields if f in results.columns]

    subset = results[available].head(max_rows).copy()

    # Round numeric columns
    for col in subset.columns:
        if subset[col].dtype in ["float64", "float32"]:
            if "pct" in col or "growth" in col or "score" in col or "adr" in col:
                subset[col] = subset[col].round(2)
            elif "price" in col or "close" in col:
                subset[col] = subset[col].round(2)

    return subset.to_string(index=False)
