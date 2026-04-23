"""
ADR% (Average Daily Range in Percent) indicator.

Measures average intraday range as percentage, EXCLUDING overnight gaps.
Formula: ADR%(N) = SMA(N) of ((High - Low) / Close * 100)

Key difference from ATR: ATR uses True Range (includes gaps).
ADR% uses only High - Low, so gap-ups don't inflate the reading.
"""

import pandas as pd


def adr_percent(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 20,
) -> pd.Series:
    """
    Calculate ADR% for a single stock.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: Lookback period (default 20)

    Returns:
        Series of ADR% values
    """
    daily_range_pct = (high - low) / close * 100
    return daily_range_pct.rolling(window=period, min_periods=period // 2).mean()


def adr_percent_bulk(
    prices_df: pd.DataFrame,
    periods: list[int] = [10, 20, 30],
) -> pd.DataFrame:
    """
    Calculate ADR% for all symbols in the prices DataFrame.

    Args:
        prices_df: DataFrame with columns [symbol, date, high, low, close]
        periods: List of lookback periods

    Returns:
        DataFrame with columns [symbol, date, adr_pct_{period}...]
    """
    results = []

    for symbol, group in prices_df.groupby("symbol"):
        group = group.sort_values("date").copy()
        for p in periods:
            group[f"adr_pct_{p}"] = adr_percent(group["high"], group["low"], group["close"], period=p)
        results.append(group)

    if not results:
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)
