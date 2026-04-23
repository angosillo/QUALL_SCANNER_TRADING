"""
Trend Intensity (TI) indicator.

Origin: Pradeep (StockBee). Measures how far the fast MA is above/below the slow MA.
Formula: TI = (SMA(fast) / SMA(slow)) * 100

Interpretation:
  > 110: Strong uptrend
  > 108: Scan threshold for "High Trending" stocks
  100:   MAs are equal — no trend
  < 92:  Strong downtrend
"""

import pandas as pd


def trend_intensity(
    close: pd.Series,
    fast: int = 13,
    slow: int = 65,
) -> pd.Series:
    """
    Calculate Trend Intensity for a single stock.

    Args:
        close: Close prices
        fast: Fast MA period (default 13)
        slow: Slow MA period (default 65)

    Returns:
        Series of TI values
    """
    sma_fast = close.rolling(window=fast, min_periods=fast // 2).mean()
    sma_slow = close.rolling(window=slow, min_periods=slow // 2).mean()
    return (sma_fast / sma_slow) * 100


def trend_intensity_bulk(
    prices_df: pd.DataFrame,
    fast: int = 13,
    slow: int = 65,
) -> pd.DataFrame:
    """
    Calculate TI for all symbols in the prices DataFrame.

    Args:
        prices_df: DataFrame with columns [symbol, date, close]
        fast: Fast MA period
        slow: Slow MA period

    Returns:
        DataFrame with added trend_intensity column
    """
    results = []

    for symbol, group in prices_df.groupby("symbol"):
        group = group.sort_values("date").copy()
        group["trend_intensity"] = trend_intensity(group["close"], fast, slow)
        results.append(group)

    if not results:
        return pd.DataFrame()

    return pd.concat(results, ignore_index=True)
