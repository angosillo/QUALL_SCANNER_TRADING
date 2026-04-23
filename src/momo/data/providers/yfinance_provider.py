"""
yfinance provider — downloads OHLCV data in batches.

Strategy: batch download ~80 tickers per request to avoid timeouts.
With 5000 tickers: ~63 batches × 2s delay = ~2-3 minutes for incremental update.
First full download (2 years): ~30-60 minutes.
"""

import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def download_batch(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """
    Download OHLCV data for a batch of tickers.
    Returns dict: ticker -> DataFrame with OHLCV columns.
    """
    tickers_str = " ".join(tickers)
    try:
        data = yf.download(
            tickers_str,
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
        )

        results = {}
        if len(tickers) == 1:
            # Single ticker — data is flat DataFrame
            if not data.empty:
                ticker = tickers[0]
                df = data[["Open", "High", "Low", "Close", "Volume"]].copy()
                df.columns = ["open", "high", "low", "close", "volume"]
                df.index.name = "date"
                results[ticker] = df
        else:
            # Multi-ticker — data has MultiIndex columns
            for ticker in tickers:
                try:
                    if ticker in data.columns.get_level_values(0):
                        df = data[ticker][["Open", "High", "Low", "Close", "Volume"]].copy()
                        df.columns = ["open", "high", "low", "close", "volume"]
                        df.index.name = "date"
                        df = df.dropna(subset=["close"])
                        if not df.empty:
                            results[ticker] = df
                except Exception:
                    continue

        return results

    except Exception as e:
        logger.warning(f"Batch download failed: {e}")
        return {}


def download_all(
    tickers: list[str],
    db_path: str,
    batch_size: int = 80,
    batch_delay: float = 2.0,
    period: str = "2y",
) -> int:
    """
    Download OHLCV for all tickers in batches. Saves to SQLite.
    Returns number of tickers successfully downloaded.
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    total = 0
    failed = []

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(tickers) + batch_size - 1) // batch_size

        logger.info(f"Batch {batch_num}/{total_batches}: {len(batch)} tickers...")
        results = download_batch(batch, period=period)

        for ticker, df in results.items():
            df = df.copy()
            df["symbol"] = ticker
            df["dollar_volume"] = df["close"] * df["volume"]
            df = df.reset_index()
            df["date"] = df["date"].astype(str)
            df.to_sql("daily_prices", conn, if_exists="append", index=False)
            total += 1

        failed.extend([t for t in batch if t not in results])

        if i + batch_size < len(tickers):
            time.sleep(batch_delay)

    conn.commit()
    conn.close()

    if failed:
        logger.warning(f"Failed to download: {len(failed)} tickers")
        if len(failed) <= 20:
            logger.warning(f"Failed tickers: {failed}")

    logger.info(f"Downloaded OHLCV for {total}/{len(tickers)} tickers")
    return total


def incremental_update(
    tickers: list[str],
    db_path: str,
    batch_size: int = 80,
    batch_delay: float = 2.0,
) -> int:
    """
    Incremental update — only fetch last 5 trading days for existing tickers.
    Much faster than full download (~5 min vs 60 min).
    """
    import sqlite3

    conn = sqlite3.connect(db_path)

    # Check what we already have
    existing = pd.read_sql(
        "SELECT DISTINCT symbol FROM daily_prices", conn
    )["symbol"].tolist()
    conn.close()

    new_tickers = [t for t in tickers if t not in existing]

    if new_tickers:
        logger.info(f"Full download for {len(new_tickers)} new tickers...")
        download_all(new_tickers, db_path, batch_size, batch_delay, period="2y")

    # Incremental for existing tickers
    existing_to_update = [t for t in tickers if t in existing]
    if not existing_to_update:
        return 0

    logger.info(f"Incremental update for {len(existing_to_update)} tickers...")
    conn = sqlite3.connect(db_path)
    total = 0

    for i in range(0, len(existing_to_update), batch_size):
        batch = existing_to_update[i : i + batch_size]
        results = download_batch(batch, period="5d")

        for ticker, df in results.items():
            df = df.copy()
            df["symbol"] = ticker
            df["dollar_volume"] = df["close"] * df["volume"]
            df = df.reset_index()
            df["date"] = df["date"].astype(str)

            # Upsert: delete existing rows for these dates, then insert
            dates = df["date"].tolist()
            placeholders = ",".join(["?"] * len(dates))
            conn.execute(
                f"DELETE FROM daily_prices WHERE symbol=? AND date IN ({placeholders})",
                [ticker] + dates,
            )
            df.to_sql("daily_prices", conn, if_exists="append", index=False)
            total += 1

        if i + batch_size < len(existing_to_update):
            time.sleep(batch_delay)

    conn.commit()
    conn.close()
    logger.info(f"Incremental update: {total} tickers")
    return total
