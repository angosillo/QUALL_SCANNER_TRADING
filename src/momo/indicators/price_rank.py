"""
Price Growth Rank — percentile ranking of price change vs entire universe.

Returns 0-100 where 100 = strongest performer in the universe.
Used to filter top N% or bottom N% of performers.
"""

import pandas as pd


def price_growth(close_wide: pd.DataFrame, period_days: int) -> pd.Series:
    """
    Calculate price growth over a period for all symbols.

    Args:
        close_wide: DataFrame (date × symbol) of close prices
        period_days: Number of trading days to look back

    Returns:
        Series indexed by symbol with % change
    """
    if close_wide.empty or len(close_wide) < period_days:
        return pd.Series(dtype=float)

    # Get the most recent and the lookback prices
    latest = close_wide.iloc[-1]
    lookback = close_wide.iloc[-period_days - 1] if len(close_wide) > period_days else close_wide.iloc[0]

    growth = (latest - lookback) / lookback * 100
    return growth.dropna()


def price_growth_rank(growth: pd.Series) -> pd.Series:
    """
    Convert raw growth values to percentile ranks (0-100).

    Args:
        growth: Series of price growth values indexed by symbol

    Returns:
        Series of percentile ranks (100 = best performer)
    """
    if growth.empty:
        return growth

    ranks = growth.rank(pct=True) * 100
    return ranks


def calculate_all_ranks(close_wide: pd.DataFrame) -> dict[str, pd.Series]:
    """
    Calculate price growth ranks for all standard timeframes.

    Returns dict with keys: rank_5d, rank_1m, rank_3m, rank_6m, rank_1y, rank_2y
    and corresponding growth values: growth_5d, growth_1m, etc.
    """
    periods = {
        "5d": 5,
        "1m": 21,       # ~1 month trading days
        "3m": 63,       # ~3 months
        "6m": 126,      # ~6 months
        "1y": 252,      # ~1 year
        "2y": 504,      # ~2 years
    }

    result = {}

    for label, days in periods.items():
        growth = price_growth(close_wide, days)
        if not growth.empty:
            result[f"growth_{label}"] = growth
            result[f"rank_{label}"] = price_growth_rank(growth)

    return result


def price_growth_bulk(
    prices_df: pd.DataFrame,
    close_wide: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate all price growth metrics and merge back into prices DataFrame.
    Returns latest row per symbol with all growth and rank columns.
    """
    ranks = calculate_all_ranks(close_wide)

    if not ranks:
        return pd.DataFrame()

    # Build result DataFrame indexed by symbol
    symbols = close_wide.columns.tolist()
    result = pd.DataFrame(index=symbols)
    result.index.name = "symbol"

    for col, series in ranks.items():
        result[col] = series

    result = result.reset_index()
    return result
